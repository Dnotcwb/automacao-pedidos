import pdfplumber
import pytesseract
from PIL import Image
import re
from unidecode import unidecode
from rapidfuzz import process, fuzz
import logging
from config import DataManager
import sys
import os
import pandas as pd

# Configuração Tesseract Windows
possible_tesseract_paths = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "Tesseract-OCR", "tesseract.exe")
]
for path in possible_tesseract_paths:
    if os.path.exists(path):
        pytesseract.pytesseract.tesseract_cmd = path
        break

class PDFProcessor:
    def __init__(self):
        self.data_manager = DataManager()
        self.valid_products_map = self.data_manager.get_valid_products_dict()
        self.valid_product_names = self.data_manager.get_valid_products_names()

    def normalize_text(self, text):
        if not text: return ""
        text = unidecode(text).upper()
        text = re.sub(r'[^\x20-\x7E\n]', '', text)
        return text

    def extract_order_id(self, full_text):
        """Extrai ID do Pedido do texto"""
        # Regex para ID do Pedido - busca padrões comuns
        match = re.search(r'(?:PEDIDO|NUMERO|N\.|NO\.)[:\s]+(\d{1,8})(?!\d)', full_text, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def detect_layout_type(self, full_text):
        """
        🔍 NOVO: Detecta qual layout o PDF segue
        
        Retorna: 'FREDDO' | 'CONDOR' | 'GENERICO'
        """
        text_upper = full_text.upper()
        
        # Markers específicos para cada layout
        is_freddo = ("GIASSI" in text_upper and "VIAREGGIO" in text_upper) or \
                    ("DESCRICAO DA MERCADORIA" in text_upper) or \
                    ("FREDDO" in text_upper)
        
        is_condor = "CONDOR SUPER CENTER" in text_upper or \
                    ("PRODUTO" in text_upper and "PRECO IPI" in text_upper)
        
        if is_freddo:
            return "FREDDO"
        elif is_condor:
            return "CONDOR"
        else:
            return "GENERICO"

    def validate_fiscal_client(self, full_text):
        """
        🔐 BUG FIX #1: CNPJ Duplicado - RESOLVIDO
        
        NOVO: Procura especificamente o CNPJ do DESTINATÁRIO/CLIENTE
        Ignora CNPJs do Emitente/Filiais
        
        Retorna: (CNPJ_valido, Motivo_Sucesso) OU (None, Motivo_Erro)
        """
        
        # 1. Tentar padrão prioritário: "DESTINATARIO:" ou "CLIENTE:"
        # Este é o CNPJ mais importante - o cliente real
        destinatario_pattern = r'(?:DESTINATARIO|CLIENTE)[:\s]*[A-Z\s]*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})'
        match_dest = re.search(destinatario_pattern, full_text, re.IGNORECASE)
        
        candidates = set()
        
        if match_dest:
            # ✅ Encontrou CNPJ após DESTINATÁRIO → usar este preferencialmente
            clean_cnpj = re.sub(r'\D', '', match_dest.group(1))
            # Validação extra: CNPJ não pode ser sequência de números iguais
            if len(set(clean_cnpj)) > 1 and len(clean_cnpj) == 14:
                candidates.add(clean_cnpj)
        
        # 2. Se não encontrou por padrão, buscar qualquer CNPJ formatado
        if not candidates:
            regex_formatted = r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}'
            matches = re.findall(regex_formatted, full_text)
            
            for m in matches:
                clean_cnpj = re.sub(r'\D', '', m)
                if len(set(clean_cnpj)) > 1 and len(clean_cnpj) == 14:
                    # Apenas adiciona o primeiro encontrado (reduz ambiguidade)
                    if clean_cnpj in self.data_manager.valid_cnpjs:
                        candidates.add(clean_cnpj)
                        break
        
        # 3. Validar contra Base de Dados (Whitelist)
        valid_candidates = [
            cnpj for cnpj in candidates 
            if cnpj in self.data_manager.valid_cnpjs
        ]
        
        # 4. Decisão Fail-Safe
        if not valid_candidates:
            if candidates:
                return None, f"REJEITADO: CNPJ encontrado ({', '.join(list(candidates)[:3])}) mas não está na whitelist."
            else:
                return None, "REJEITADO: Nenhum padrão de CNPJ encontrado no PDF."
        
        # ✅ SUCESSO: Retorna o primeiro (e único) CNPJ válido
        return list(valid_candidates)[0], "VALIDADO"

    def get_filial_info(self, cnpj):
        """Busca informações da filial baseado no CNPJ"""
        if not cnpj: 
            return ""
        try:
            row = self.data_manager.df_clientes[
                self.data_manager.df_clientes['id_cliente_teknisa'] == cnpj
            ].iloc[0]
            if 'id_filial_destino' in row and pd.notna(row['id_filial_destino']):
                return str(row['id_filial_destino']).replace('.0', '').strip()
        except:
            return ""
        return ""

    def extract_products_freddo(self, page, id_cliente):
        """
        🔧 BUG FIX #2: Layout FREDDO específico
        
        Características:
        - Tabela em cascata com múltiplos pedidos
        - Produto, Código, Quantidade na mesma linha/contexto
        - Código em coluna "Cod/Ean/Dun14"
        """
        words = page.extract_words(x_tolerance=3, y_tolerance=3)
        extracted = []
        
        # Agrupa palavras por linha (Y similar)
        lines_dict = {}
        for w in words:
            y_rounded = round(w['top'] / 5) * 5
            if y_rounded not in lines_dict:
                lines_dict[y_rounded] = []
            lines_dict[y_rounded].append(w)
        
        sorted_y = sorted(lines_dict.keys())
        
        for y in sorted_y:
            line_words = sorted(lines_dict[y], key=lambda x: x['x0'])
            line_text = " ".join([w['text'] for w in line_words])
            line_text_norm = self.normalize_text(line_text)
            
            product_id = None
            product_x = None
            
            # A) Buscar código do produto (prioridade: é mais confiável)
            potential_codes = re.findall(r'\b\d{8,14}\b', line_text_norm)
            for code in potential_codes:
                if code in self.valid_products_map:
                    product_id = code
                    # Encontra a posição X do código para buscar quantidade próxima
                    for w in line_words:
                        if code in w['text'].replace('.', '').replace('-', ''):
                            product_x = w['x0']
                            break
                    break
            
            # B) Se não achou código, tenta nome fuzzy
            if not product_id:
                text_only = re.sub(r'\d+', '', line_text_norm)
                if len(text_only) > 10:
                    match = process.extractOne(text_only, self.valid_product_names, 
                                             scorer=fuzz.token_set_ratio)
                    if match and match[1] > 92:
                        p_name = match[0]
                        try:
                            product_id = self.data_manager.df_produtos[
                                self.data_manager.df_produtos['Nome do Produto'] == p_name
                            ]['Código'].values[0]
                            product_x = line_words[0]['x0'] if line_words else 0
                        except:
                            pass
            
            # Se encontrou produto, busca quantidade
            if product_id:
                qtd_final = 0
                
                candidates = []
                for w in line_words:
                    clean_w = re.sub(r'\D', '', w['text'])
                    if clean_w:
                        try:
                            val = int(clean_w)
                        except:
                            continue
                        
                        # 🔧 BUG FIX #3: Filtros mais rigorosos para quantidade
                        # Evita pegar número errado (preço, CNPJ, ID, etc)
                        
                        if str(val) in str(product_id):
                            continue  # É parte do ID do produto
                        if str(val) in id_cliente:
                            continue  # É parte do CNPJ
                        if val == 0:
                            continue  # Zero não é quantidade válida
                        if val < 1:
                            continue  # Quantidade deve ser >= 1
                        if val > 10000:
                            continue  # Quantidade impossível
                        
                        # ✅ Candidato válido
                        candidates.append({'val': val, 'x': w['x0']})
                
                if candidates:
                    # Pega o candidato mais à direita (melhor heurística para layouts em cascata)
                    best_candidate = sorted(candidates, key=lambda c: c['x'])[-1]
                    qtd_final = best_candidate['val']
                
                extracted.append({
                    "ID_Pedido": "",  # Será preenchido após
                    "ID_FilialDestino": "",
                    "ID_Cliente": id_cliente,
                    "ID_Produto": product_id,
                    "Quantidade": qtd_final
                })
        
        return extracted

    def extract_products_condor(self, page, id_cliente):
        """
        🔧 BUG FIX #2: Layout CONDOR específico
        
        Características:
        - Código do produto pode estar em linha separada
        - Coluna "Qtde" tem a quantidade
        - Formatação mais espaçada
        """
        words = page.extract_words(x_tolerance=3, y_tolerance=3)
        extracted = []
        
        # Agrupa palavras por linha
        lines_dict = {}
        for w in words:
            y_rounded = round(w['top'] / 4) * 4  # Tolerance menor para Condor
            if y_rounded not in lines_dict:
                lines_dict[y_rounded] = []
            lines_dict[y_rounded].append(w)
        
        sorted_y = sorted(lines_dict.keys())
        
        i = 0
        while i < len(sorted_y):
            y = sorted_y[i]
            line_words = sorted(lines_dict[y], key=lambda x: x['x0'])
            line_text = " ".join([w['text'] for w in line_words])
            line_text_norm = self.normalize_text(line_text)
            
            product_id = None
            
            # Buscar código
            potential_codes = re.findall(r'\b\d{8,14}\b', line_text_norm)
            for code in potential_codes:
                if code in self.valid_products_map:
                    product_id = code
                    break
            
            # Se encontrou produto
            if product_id:
                qtd_final = 0
                
                # Em layout Condor, quantidade geralmente está na mesma linha
                candidates = []
                for w in line_words:
                    clean_w = re.sub(r'\D', '', w['text'])
                    if clean_w:
                        try:
                            val = int(clean_w)
                        except:
                            continue
                        
                        # Mesmos filtros de FREDDO
                        if str(val) in str(product_id):
                            continue
                        if str(val) in id_cliente:
                            continue
                        if val == 0 or val < 1:
                            continue
                        if val > 10000:
                            continue
                        
                        candidates.append({'val': val, 'x': w['x0']})
                
                if candidates:
                    # Em layout Condor, quantidade tende a estar mais à direita
                    best_candidate = sorted(candidates, key=lambda c: c['x'])[-1]
                    qtd_final = best_candidate['val']
                
                extracted.append({
                    "ID_Pedido": "",
                    "ID_FilialDestino": "",
                    "ID_Cliente": id_cliente,
                    "ID_Produto": product_id,
                    "Quantidade": qtd_final
                })
            
            i += 1
        
        return extracted

    def extract_products_generic(self, page, id_cliente):
        """
        Fallback: Lógica genérica para layouts desconhecidos
        Usa melhor heurística possível
        """
        words = page.extract_words(x_tolerance=3, y_tolerance=3)
        extracted = []
        
        lines_dict = {}
        for w in words:
            y_rounded = round(w['top'] / 5) * 5
            if y_rounded not in lines_dict:
                lines_dict[y_rounded] = []
            lines_dict[y_rounded].append(w)
        
        sorted_y = sorted(lines_dict.keys())
        
        for y in sorted_y:
            line_words = sorted(lines_dict[y], key=lambda x: x['x0'])
            line_text = " ".join([w['text'] for w in line_words])
            line_text_norm = self.normalize_text(line_text)
            
            product_id = None
            
            # A) Código
            potential_codes = re.findall(r'\b\d{8,14}\b', line_text_norm)
            for code in potential_codes:
                if code in self.valid_products_map:
                    product_id = code
                    break
            
            # B) Nome Fuzzy
            if not product_id:
                text_only = re.sub(r'\d+', '', line_text_norm)
                if len(text_only) > 10:
                    match = process.extractOne(text_only, self.valid_product_names, 
                                             scorer=fuzz.token_set_ratio)
                    if match and match[1] > 92:
                        p_name = match[0]
                        try:
                            product_id = self.data_manager.df_produtos[
                                self.data_manager.df_produtos['Nome do Produto'] == p_name
                            ]['Código'].values[0]
                        except:
                            pass
            
            if product_id:
                qtd_final = 0
                
                candidates = []
                for w in line_words:
                    clean_w = re.sub(r'\D', '', w['text'])
                    if clean_w:
                        try:
                            val = int(clean_w)
                        except:
                            continue
                        
                        if str(val) in str(product_id):
                            continue
                        if str(val) in id_cliente:
                            continue
                        if val == 0 or val < 1:
                            continue
                        if val > 10000:
                            continue
                        
                        candidates.append({'val': val, 'x': w['x0']})
                
                if candidates:
                    best_candidate = sorted(candidates, key=lambda c: c['x'])[-1]
                    qtd_final = best_candidate['val']
                
                extracted.append({
                    "ID_Pedido": "",
                    "ID_FilialDestino": "",
                    "ID_Cliente": id_cliente,
                    "ID_Produto": product_id,
                    "Quantidade": qtd_final
                })
        
        return extracted

    def process_pdf(self, pdf_path, filename):
        """
        Processa PDF completo com validação fiscal e extração de produtos
        """
        full_text_accumulated = ""
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # FASE 1: LEITURA INTEGRAL PARA VALIDAÇÃO
                for page in pdf.pages:
                    txt = page.extract_text() or ""
                    full_text_accumulated += self.normalize_text(txt) + "\n"
                
                # FASE 2: GATEKEEPER FISCAL (BUG FIX #1)
                id_cliente, status_msg = self.validate_fiscal_client(full_text_accumulated)
                
                # SE FALHAR NA VALIDAÇÃO FISCAL, ABORTA IMEDIATAMENTE
                if not id_cliente:
                    print(f"   ⛔ PDF Rejeitado: {status_msg}")
                    return {
                        'status': 'REJEITADO',
                        'motivo': status_msg,
                        'arquivo': filename,
                        'itens': []
                    }
                
                # Se passou, recupera dados auxiliares
                id_filial = self.get_filial_info(id_cliente)
                id_pedido = self.extract_order_id(full_text_accumulated)
                print(f"   ✅ Cliente Validado: {id_cliente} | Pedido: {id_pedido}")
                
                # DETECTAR LAYOUT (BUG FIX #2)
                layout_type = self.detect_layout_type(full_text_accumulated)
                print(f"   📋 Layout detectado: {layout_type}")
                
                extracted_items = []
                
                # FASE 3: EXTRAÇÃO DE PRODUTOS (Somente para clientes validados)
                # ESPECÍFICA POR LAYOUT (BUG FIX #2)
                for page in pdf.pages:
                    if layout_type == "FREDDO":
                        items = self.extract_products_freddo(page, id_cliente)
                    elif layout_type == "CONDOR":
                        items = self.extract_products_condor(page, id_cliente)
                    else:
                        items = self.extract_products_generic(page, id_cliente)
                    
                    # Preenche dados do pedido e filial
                    for item in items:
                        item["ID_Pedido"] = id_pedido
                        item["ID_FilialDestino"] = id_filial
                    
                    extracted_items.extend(items)
                
                # Retorno de Sucesso
                if not extracted_items:
                    return {
                        'status': 'REJEITADO', 
                        'motivo': 'CNPJ validado, mas nenhum produto identificado no layout.',
                        'arquivo': filename,
                        'itens': []
                    }
                
                return {
                    'status': 'SUCESSO',
                    'motivo': 'Importação Válida',
                    'arquivo': filename,
                    'itens': extracted_items
                }
        
        except Exception as e:
            logging.error(f"Erro processando {filename}: {e}")
            return {
                'status': 'ERRO_SISTEMA', 
                'motivo': str(e), 
                'arquivo': filename, 
                'itens': []
            }
