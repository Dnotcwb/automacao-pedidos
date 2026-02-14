"""
>>> SISTEMA DE IMPORTAÇÃO FISCAL (FAIL-SAFE MODE)

Este arquivo pode ser usado de 2 formas:
1. Via GUI: Execute app.py (interface amigável)
2. Via Terminal: Execute este arquivo (automação original)

Versão: 1.0 Corrigida (com fixes de CNPJ, layouts e quantidade)
Data: 14/02/2026
"""

import os
import glob
import pandas as pd
from processor import PDFProcessor
from config import DataManager
import sys
import time
from datetime import datetime

print(">>> SISTEMA DE IMPORTAÇÃO FISCAL (FAIL-SAFE MODE)")

def main():
    """Processa PDFs em modo terminal (sem GUI)"""
    
    print("="*60)
    print("VALIDAÇÃO RÍGIDA DE CNPJ ATIVADA")
    print("Arquivos sem CNPJ validado serão enviados para Auditoria.")
    print("="*60)

    try:
        print(">>> Carregando tabelas e Whitelist de CNPJs...")
        manager = DataManager()
        processor = PDFProcessor()
        print("✅ Dados carregados com sucesso")
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        return

    input_folder = "entrada_pdfs"
    if not os.path.exists(input_folder):
        os.makedirs(input_folder)
        print(f"📁 Pasta '{input_folder}' criada. Coloque seus PDFs lá.")
        return

    pdf_files = glob.glob(os.path.join(input_folder, "*.pdf"))
    if not pdf_files:
        print(f"⚠️  Nenhum PDF encontrado em '{input_folder}'.")
        return

    print(f"📄 Encontrados {len(pdf_files)} arquivo(s).")
    
    # Listas segregadas
    valid_data = []
    rejected_data = []

    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        print(f"\n🔄 Processando: {filename} ...")
        
        result = processor.process_pdf(pdf_path, filename)
        
        if result['status'] == 'SUCESSO':
            print(f"   ✅ ACEITO: {len(result['itens'])} linhas geradas.")
            valid_data.extend(result['itens'])
        else:
            print(f"   ❌ REJEITADO: {result['motivo']}")
            rejected_data.append({
                'Arquivo': filename,
                'Status': result['status'],
                'Motivo_Rejeicao': result['motivo'],
                'Data_Processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. GERAÇÃO DO ARQUIVO DE IMPORTAÇÃO (APENAS DADOS VÁLIDOS)
    if valid_data:
        print("\n>>> Gerando Excel de Importação (ERP)...")
        df_import = pd.DataFrame(valid_data)
        
        # Filtro estrito de colunas
        target_columns = ["ID_Pedido", "ID_FilialDestino", "ID_Cliente", "ID_Produto", "Quantidade"]
        df_final = pd.DataFrame(columns=target_columns)
        for col in target_columns:
            if col in df_import.columns:
                df_final[col] = df_import[col]
        
        df_final = df_final.fillna("")
        
        # Salva em pasta saida_importacao
        if not os.path.exists('saida_importacao'):
            os.makedirs('saida_importacao')
        
        name_import = f"saida_importacao/Importacao_ERP_{timestamp}.xlsx"
        df_final.to_excel(name_import, index=False)
        print(f"🚀 [IMPORTAÇÃO] Arquivo gerado: {name_import}")
        print(f"📊 Total de linhas válidas: {len(df_final)}")
    else:
        print("\n⚠️ NENHUM pedido válido foi gerado para importação.")

    # 2. GERAÇÃO DO RELATÓRIO DE AUDITORIA (REJEITADOS)
    if rejected_data:
        print("\n>>> Gerando Relatório de Auditoria (Rejeitados)...")
        df_audit = pd.DataFrame(rejected_data)
        
        # Salva em pasta saida_auditoria
        if not os.path.exists('saida_auditoria'):
            os.makedirs('saida_auditoria')
        
        name_audit = f"saida_auditoria/Relatorio_Auditoria_Rejeitados_{timestamp}.xlsx"
        df_audit.to_excel(name_audit, index=False)
        print(f"🛡️ [AUDITORIA] Arquivo gerado: {name_audit}")
        print(f"📊 Total de arquivos rejeitados: {len(df_audit)}")

    print("\n" + "="*60)
    print("PROCESSAMENTO CONCLUÍDO")
    print("="*60)

if __name__ == "__main__":
    main()
    input("\nPressione ENTER para sair...")
