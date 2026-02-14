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
        # Regex para ID do Pedido
        match = re.search(r'(PEDIDO|NUMERO|N\.|NO\.)[:\s]+(\d{1,8})(?!\d)', full_text)
        if match:
            return match.group(2)
        return ""

    def validate_fiscal_client(self, full_text):
        """
        GATEKEEPER FISCAL:
        Procura CNPJs no texto e valida contra a WhiteList do Excel.
        Retorna: (CNPJ, Motivo_Sucesso) OU (None, Motivo_Erro)
        """
        # 1. Busca regex ampla de números que parecem CNPJ (14 digitos)
        # Procura tanto formatado (XX.XXX...) quanto limpo
        regex_formatted = r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}'
        regex_clean = r'\b\d{14}\b'
        
        matches_formatted = re.findall(regex_formatted, full_text)
        matches_clean = re.findall(regex_clean, full_text)
        
        candidates = set()
        
        # Normaliza tudo encontrado para apenas números
        for m in matches_formatted + matches_clean:
            clean_cnpj = re.sub(r'\D', '', m)
            # Filtro extra: CNPJ não pode ser sequência de numeros iguais (ex: 11111) ou zeros
            if len(set(clean_cnpj)) > 1: 
                candidates.add(clean_cnpj)
            
        # 2. Validação contra Base de Dados (Whitelist)
        valid_candidates = []
        for cnpj in candidates:
            if cnpj in self.data_manager.valid_cnpjs:
                valid_candidates.append(cnpj)
        
        # 3. Decisão Fail-Safe
        if len(valid_candidates) == 0:
            if len(candidates) > 0:
                return None, f"REJEITADO: CNPJs encontrados no PDF ({', '.join(list(candidates)[:3])}) não estão cadastrados no mapeamento."
            else:
                return None, "REJEITADO: Nenhum padrão de CNPJ encontrado no PDF."
                
        elif len(valid_candidates) > 1:
            return None, f"REJEITADO: Ambiguidade Fiscal. Múltiplos CNPJs válidos encontrados: {', '.join(valid_candidates)}"
            
        else:
            # SUCESSO: Exatamente 1 match válido
            return valid_candidates[0], "VALIDADO"

    def get_filial_info(self, cnpj):
        if not cnpj: return ""
        try:
            row = self.data_manager.df_clientes[self.data_manager.df_clientes['id_cliente_teknisa'] == cnpj].iloc[0]
            if 'id_filial_destino' in row and pd.notna(row['id_filial_destino']):
                return str(row['id_filial_destino']).replace('.0', '').strip()
        except:
            return ""
        return ""

    def process_pdf(self, pdf_path, filename):
        full_text_accumulated = ""
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # FASE 1: LEITURA INTEGRAL PARA VALIDAÇÃO
                for page in pdf.pages:
                    txt = page.extract_text() or ""
                    full_text_accumulated += self.normalize_text(txt) + "\n"
                
                # FASE 2: GATEKEEPER FISCAL
                id_cliente, status_msg = self.validate_fiscal_client(full_text_accumulated)
                
                # SE FALHAR NA VALIDAÇÃO FISCAL, ABORTA IMEDIATAMENTE.
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
                print(f"   🔒 Cliente Validado: {id_cliente} | Pedido: {id_pedido}")

                extracted_items = []

                # FASE 3: EXTRAÇÃO DE PRODUTOS (Somente para clientes validados)
                for page in pdf.pages:
                    words = page.extract_words(x_tolerance=3, y_tolerance=3)
                    
                    # Agrupa linhas
                    lines_dict = {}
                    for w in words:
                        y_rounded = round(w['top'] / 5) * 5
                        if y_rounded not in lines_dict: lines_dict[y_rounded] = []
                        lines_dict[y_rounded].append(w)
                    
                    sorted_y = sorted(lines_dict.keys())
                    
                    for y in sorted_y:
                        line_words = sorted(lines_dict[y], key=lambda x: x['x0'])
                        line_text = " ".join([w['text'] for w in line_words])
                        line_text_norm = self.normalize_text(line_text)
                        
                        # Busca Produto
                        product_id = None
                        
                        # A) Código
                        potential_codes = re.findall(r'\b\d{8,14}\b', line_text_norm)
                        for code in potential_codes:
                            if code in self.valid_products_map:
                                product_id = code
                                break
                        
                        # B) Nome Fuzzy (Só se não achou código)
                        if not product_id:
                            text_only = re.sub(r'\d+', '', line_text_norm)
                            if len(text_only) > 10:
                                match = process.extractOne(text_only, self.valid_product_names, scorer=fuzz.token_set_ratio)
                                if match and match[1] > 92:
                                    p_name = match[0]
                                    try:
                                        product_id = self.data_manager.df_produtos[self.data_manager.df_produtos['Nome do Produto'] == p_name]['Código'].values[0]
                                    except: pass

                        if product_id:
                            qtd_final = 0 # Default seguro, melhor 0 do que lixo
                            
                            # Busca quantidade à direita do produto
                            candidates = []
                            for w in line_words:
                                clean_w = re.sub(r'\D', '', w['text'])
                                if clean_w:
                                    val = int(clean_w)
                                    # Filtro de segurança:
                                    if str(val) in str(product_id): continue  # É parte do ID
                                    if str(val) in id_cliente: continue # É parte do CNPJ
                                    if val == 0: continue
                                    if val < 5000: # Quantidade plausível
                                        candidates.append({'val': val, 'x': w['x0']})
                            
                            if candidates:
                                # Pega o candidato mais à direita
                                best_candidate = sorted(candidates, key=lambda c: c['x'])[-1]
                                qtd_final = best_candidate['val']

                            extracted_items.append({
                                "ID_Pedido": id_pedido,
                                "ID_FilialDestino": id_filial,
                                "ID_Cliente": id_cliente,
                                "ID_Produto": product_id,
                                "Quantidade": qtd_final
                            })
                
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
            return {'status': 'ERRO_SISTEMA', 'motivo': str(e), 'arquivo': filename, 'itens': []}
