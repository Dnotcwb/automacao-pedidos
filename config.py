import pandas as pd
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
            self.df_clientes['id_cliente_teknisa'] = self.df_clientes['id_cliente_teknisa'].str.replace(r'\.0$', '', regex=True)
            self.df_clientes['id_cliente_teknisa'] = self.df_clientes['id_cliente_teknisa'].str.replace(r'\D', '', regex=True)
            
            # Cria um SET de CNPJs válidos para validação O(1)
            # Apenas CNPJs com 14 dígitos são considerados válidos para importação
            self.valid_cnpjs = set(
                cnpj for cnpj in self.df_clientes['id_cliente_teknisa'].dropna().unique() 
                if len(cnpj) == 14
            )

            # --- PRODUTOS ---
            self.df_produtos = pd.read_excel("Relatorio potes.xlsx", dtype={'Código': str})
            self.df_produtos['Código'] = self.df_produtos['Código'].str.replace(r'\D', '', regex=True)
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
