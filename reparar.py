import os
import sys
import subprocess
import importlib

# --- 1. CONFIGURAÇÃO (STRICT MODE) ---
CONTENT_CONFIG = """import pandas as pd
import logging
import os
import re

logging.basicConfig(
    filename='processamento_pedidos.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

class DataManager:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataManager, cls).__new__(cls)
            cls._instance.load_data()
        return cls._instance

    def load_data(self):
        print("📂 Carregando bases de dados (Excel)...")
        try:
            # --- CLIENTES (BASE DE VALIDAÇÃO) ---
            # Carrega forçando tudo como string
            self.df_clientes = pd.read_excel(
                "mapeamento_teknisa.xlsx", 
                sheet_name="DePara_Clientes", 
                dtype={'id_cliente_teknisa': str, 'chave_identificacao_pdf': str}
            )
            
            # Normalização Rígida do CNPJ (Apenas números)
            self.df_clientes['id_cliente_teknisa'] = self.df_clientes['id_cliente_teknisa'].astype(str)
            self.df_clientes['id_cliente_teknisa'] = self.df_clientes['id_cliente_teknisa'].str.replace(r'\\.0$', '', regex=True)
            self.df_clientes['id_cliente_teknisa'] = self.df_clientes['id_cliente_teknisa'].str.replace(r'\\D', '', regex=True)
            
            # Cria um SET de CNPJs válidos para validação O(1)
            # Apenas CNPJs com 14 dígitos são considerados válidos para importação
            self.valid_cnpjs = set(
                cnpj for cnpj in self.df_clientes['id_cliente_teknisa'].dropna().unique() 
                if len(cnpj) == 14
            )

            # --- PRODUTOS ---
            self.df_produtos = pd.read_excel("Relatorio potes.xlsx", dtype={'Código': str})
            self.df_produtos['Código'] = self.df_produtos['Código'].str.replace(r'\\D', '', regex=True)
            self.df_produtos['Nome do Produto'] = self.df_produtos['Nome do Produto'].astype(str).str.upper().str.strip()
            
            print(f"✅ DADOS FISCAIS: {len(self.valid_cnpjs)} CNPJs válidos carregados para whitelist.")
            
        except Exception as e:
            logging.critical(f"Erro ao carregar arquivos Excel de referência: {e}")
            print(f"❌ ERRO CRÍTICO DE DADOS: {e}")
            raise e

    def get_valid_products_dict(self):
        return dict(zip(self.df_produtos['Código'], self.df_produtos['Nome do Produto']))

    def get_valid_products_names(self):
        return self.df_produtos['Nome do Produto'].tolist()
"""

# --- 2. PROCESSADOR (FAIL-SAFE ARCHITECTURE) ---
CONTENT_PROCESSOR = """import pdfplumber
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
    r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
    r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
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
        text = re.sub(r'[^\\x20-\\x7E\\n]', '', text)
        return text

    def extract_order_id(self, full_text):
        # Regex para ID do Pedido
        match = re.search(r'(PEDIDO|NUMERO|N\.|NO\.)[:\\s]+(\\d{1,8})(?!\\d)', full_text)
        if match:
            return match.group(2)
        return ""

    def validate_fiscal_client(self, full_text):
        \"\"\"
        GATEKEEPER FISCAL:
        Procura CNPJs no texto e valida contra a WhiteList do Excel.
        Retorna: (CNPJ, Motivo_Sucesso) OU (None, Motivo_Erro)
        \"\"\"
        # 1. Busca regex ampla de números que parecem CNPJ (14 digitos)
        # Procura tanto formatado (XX.XXX...) quanto limpo
        regex_formatted = r'\\d{2}\\.\\d{3}\\.\\d{3}/\\d{4}-\\d{2}'
        regex_clean = r'\\b\\d{14}\\b'
        
        matches_formatted = re.findall(regex_formatted, full_text)
        matches_clean = re.findall(regex_clean, full_text)
        
        candidates = set()
        
        # Normaliza tudo encontrado para apenas números
        for m in matches_formatted + matches_clean:
            clean_cnpj = re.sub(r'\\D', '', m)
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
                    full_text_accumulated += self.normalize_text(txt) + "\\n"
                
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
                        potential_codes = re.findall(r'\\b\\d{8,14}\\b', line_text_norm)
                        for code in potential_codes:
                            if code in self.valid_products_map:
                                product_id = code
                                break
                        
                        # B) Nome Fuzzy (Só se não achou código)
                        if not product_id:
                            text_only = re.sub(r'\\d+', '', line_text_norm)
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
                                clean_w = re.sub(r'\\D', '', w['text'])
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
"""

# --- 3. ORQUESTRADOR (SEPARAÇÃO DE FLUXOS) ---
CONTENT_MAIN = """import os
import glob
import pandas as pd
from processor import PDFProcessor
from config import DataManager
import sys
import time
from datetime import datetime

print(">>> SISTEMA DE IMPORTAÇÃO FISCAL (FAIL-SAFE MODE)")

def main():
    print("="*60)
    print("VALIDAÇÃO RÍGIDA DE CNPJ ATIVADA")
    print("Arquivos sem CNPJ validado serão enviados para Auditoria.")
    print("="*60)

    try:
        print(">>> Carregando tabelas e Whitelist de CNPJs...")
        manager = DataManager()
        processor = PDFProcessor()
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        return

    input_folder = "entrada_pdfs"
    if not os.path.exists(input_folder):
        os.makedirs(input_folder)
        return

    pdf_files = glob.glob(os.path.join(input_folder, "*.pdf"))
    if not pdf_files:
        print(f"⚠️  Nenhum PDF encontrado em '{input_folder}'.")
        return

    print(f"📄 Encontrados {len(pdf_files)} arquivos.")
    
    # Listas segregadas
    valid_data = []
    rejected_data = []

    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        print(f"\\n🔄 Processando: {filename} ...")
        
        result = processor.process_pdf(pdf_path, filename)
        
        if result['status'] == 'SUCESSO':
            print(f"   ✅ ACEITO: {len(result['itens'])} linhas geradas.")
            valid_data.extend(result['itens'])
        else:
            print(f"   ⛔ REJEITADO: {result['motivo']}")
            rejected_data.append({
                'Arquivo': filename,
                'Status': result['status'],
                'Motivo_Rejeicao': result['motivo'],
                'Data_Processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. GERAÇÃO DO ARQUIVO DE IMPORTAÇÃO (APENAS DADOS VÁLIDOS)
    if valid_data:
        print("\\n>>> Gerando Excel de Importação (ERP)...")
        df_import = pd.DataFrame(valid_data)
        
        # Filtro estrito de colunas
        target_columns = ["ID_Pedido", "ID_FilialDestino", "ID_Cliente", "ID_Produto", "Quantidade"]
        df_final = pd.DataFrame(columns=target_columns)
        for col in target_columns:
            if col in df_import.columns:
                df_final[col] = df_import[col]
        
        df_final = df_final.fillna("")
        
        name_import = f"Importacao_ERP_{timestamp}.xlsx"
        df_final.to_excel(name_import, index=False)
        print(f"🚀 [IMPORTAÇÃO] Arquivo gerado: {name_import}")
        print(f"📊 Total de linhas válidas: {len(df_final)}")
    else:
        print("\\n⚠️ NENHUM pedido válido foi gerado para importação.")

    # 2. GERAÇÃO DO RELATÓRIO DE AUDITORIA (REJEITADOS)
    if rejected_data:
        print("\\n>>> Gerando Relatório de Auditoria (Rejeitados)...")
        df_audit = pd.DataFrame(rejected_data)
        name_audit = f"Relatorio_Auditoria_Rejeitados_{timestamp}.xlsx"
        df_audit.to_excel(name_audit, index=False)
        print(f"🛡️ [AUDITORIA] Arquivo gerado: {name_audit}")
        print(f"📊 Total de arquivos rejeitados: {len(df_audit)}")

    print("="*60)
    print("PROCESSAMENTO CONCLUÍDO")

if __name__ == "__main__":
    main()
    input("\\nPressione ENTER para sair...")
"""

# --- ATUALIZADOR ---
CONTENT_REQUIREMENTS = """pandas==2.2.0
openpyxl==3.1.2
pdfplumber==0.10.3
pytesseract==0.3.10
rapidfuzz==3.6.1
unidecode==1.3.8
Pillow==10.2.0"""

print("🔧 APLICANDO ARQUITETURA FAIL-SAFE...")
files_to_check = {
    "requirements.txt": CONTENT_REQUIREMENTS,
    "config.py": CONTENT_CONFIG,
    "processor.py": CONTENT_PROCESSOR,
    "main.py": CONTENT_MAIN
}
for filename, content in files_to_check.items():
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Arquivo: {filename:<15} | Status: BLINDADO")

if not os.path.exists("entrada_pdfs"): os.makedirs("entrada_pdfs")
print("-" * 50)
print("✅ SISTEMA FAIL-SAFE ATIVO!")
print("👉 PDFs sem CNPJ válido serão rejeitados automaticamente.")
print("👉 Rode: python main.py")
input("Pressione ENTER para fechar...")