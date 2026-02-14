"""
🎯 AUTOMAÇÃO DE PEDIDOS EM PDF - INTERFACE GRÁFICA
Versão: 1.0
Data: 14/02/2026

Interface PySimpleGUI para processar PDFs de forma amigável
Sem necessidade de usar terminal ou linha de comando
"""

import PySimpleGUI as sg
from processor import PDFProcessor
from config import DataManager
import os
import glob
from datetime import datetime
import pandas as pd
import threading

# Configuração de tema visual
sg.theme('DarkBlue2')
sg.set_options(font=('Arial', 10))


class GUIApp:
    """Aplicação gráfica para automação de pedidos"""
    
    def __init__(self):
        """Inicializa a aplicação"""
        try:
            print("🔧 Inicializando aplicação...")
            self.processor = PDFProcessor()
            self.manager = DataManager()
            self.selected_folder = None
            self.window = None
            self.processing = False
            
            # Criar pastas necessárias
            self.ensure_folders()
            
            print("✅ Aplicação iniciada com sucesso")
        except Exception as e:
            sg.popup_error(f"❌ Erro ao inicializar: {e}")
            raise e
    
    def ensure_folders(self):
        """Cria pastas necessárias se não existirem"""
        folders = ['entrada_pdfs', 'saida_importacao', 'saida_auditoria']
        for folder in folders:
            if not os.path.exists(folder):
                os.makedirs(folder)
                print(f"📁 Pasta criada: {folder}")
    
    def create_window(self):
        """
        Cria a janela principal da interface
        
        Layout:
        - Título
        - Campo de seleção de pasta
        - Área de log com status de processamento
        - Botões de ação
        """
        
        layout = [
            # ===== CABEÇALHO =====
            [sg.Text('🎯 AUTOMAÇÃO DE PEDIDOS EM PDF', 
                    font=('Arial', 16, 'bold'), text_color='white')],
            
            [sg.HorizontalSeparator()],
            
            # ===== SELEÇÃO DE PASTA =====
            [sg.Text('📁 Pasta de PDFs:')],
            [sg.InputText(key='FOLDER', size=(50, 1), disabled=True),
             sg.FolderBrowse('📂 Selecionar Pasta', key='BROWSE', target='FOLDER')],
            
            [sg.Text('(Coloque seus PDFs nesta pasta e clique em "Processar")', 
                    font=('Arial', 9), text_color='gray')],
            
            [sg.HorizontalSeparator()],
            
            # ===== ÁREA DE LOG =====
            [sg.Text('📋 Status de Processamento:')],
            [sg.Multiline(
                size=(70, 20), 
                key='LOG', 
                disabled=True,
                autoscroll=True,
                background_color='black',
                text_color='white',
                font=('Courier New', 9)
            )],
            
            [sg.HorizontalSeparator()],
            
            # ===== BOTÕES DE AÇÃO =====
            [
                sg.Button('🚀 PROCESSAR', key='PROCESS', size=(15, 1), 
                         button_color=('white', 'green')),
                sg.Button('📂 Abrir Resultado', key='OPEN_RESULT', size=(15, 1)),
                sg.Button('❌ Sair', key='EXIT', size=(15, 1))
            ],
            
            # ===== BARRA DE PROGRESSO =====
            [sg.ProgressBar(100, orientation='h', size=(70, 15), key='PROGRESS_BAR')],
            
            [sg.Text('Pronto para processar', key='STATUS_TEXT', text_color='lightgreen')]
        ]
        
        return sg.Window(
            'Automação de Pedidos em PDF - v1.0',
            layout,
            finalize=True,
            size=(850, 750)
        )
    
    def log_message(self, message):
        """
        Adiciona mensagem ao log visual
        
        Args:
            message (str): Mensagem a adicionar
        """
        if self.window:
            current_log = self.window['LOG'].get()
            timestamp = datetime.now().strftime("%H:%M:%S")
            new_log = f"{current_log}{timestamp} {message}\n"
            self.window['LOG'].update(new_log)
            # Scroll automático para o final
            self.window['LOG'].set_vscroll_position(1.0)
    
    def update_progress(self, value):
        """Atualiza barra de progresso"""
        if self.window:
            self.window['PROGRESS_BAR'].update_bar(min(value, 100))
    
    def process_folder(self, folder_path):
        """
        Processa todos os PDFs da pasta selecionada
        
        Args:
            folder_path (str): Caminho da pasta com PDFs
        """
        self.processing = True
        self.log_message("=" * 70)
        self.log_message("🔄 INICIANDO PROCESSAMENTO...")
        self.log_message("=" * 70)
        
        try:
            # Encontra todos os PDFs
            pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))
            
            if not pdf_files:
                self.log_message("⚠️  Nenhum arquivo PDF encontrado na pasta selecionada")
                self.processing = False
                return
            
            self.log_message(f"📄 Encontrados {len(pdf_files)} arquivo(s)")
            self.log_message("")
            
            # Listas para segregar resultados
            valid_data = []
            rejected_data = []
            
            # Processa cada PDF
            for idx, pdf_path in enumerate(pdf_files):
                filename = os.path.basename(pdf_path)
                
                # Atualiza progresso
                progress = int((idx / len(pdf_files)) * 100)
                self.update_progress(progress)
                
                self.log_message(f"[{idx + 1}/{len(pdf_files)}] 🔄 Processando: {filename}")
                
                # Processa PDF
                result = self.processor.process_pdf(pdf_path, filename)
                
                # Registra resultado
                if result['status'] == 'SUCESSO':
                    self.log_message(f"                    ✅ ACEITO: {len(result['itens'])} linhas geradas")
                    valid_data.extend(result['itens'])
                else:
                    motivo = result['motivo'][:60]  # Trunca motivo longo
                    self.log_message(f"                    ❌ REJEITADO: {motivo}")
                    rejected_data.append({
                        'Arquivo': filename,
                        'Status': result['status'],
                        'Motivo_Rejeicao': result['motivo'],
                        'Data_Processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                
                self.log_message("")
            
            # Completa barra de progresso
            self.update_progress(100)
            
            # Gera arquivos de saída
            self.log_message("=" * 70)
            self.log_message("📊 GERANDO ARQUIVOS DE SAÍDA...")
            self.log_message("=" * 70)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 1. GERAR ARQUIVO DE IMPORTAÇÃO (DADOS VÁLIDOS)
            if valid_data:
                self.log_message("✏️  Gerando arquivo de importação...")
                df_import = pd.DataFrame(valid_data)
                
                # Filtro estrito de colunas
                target_columns = ["ID_Pedido", "ID_FilialDestino", "ID_Cliente", "ID_Produto", "Quantidade"]
                df_final = pd.DataFrame(columns=target_columns)
                for col in target_columns:
                    if col in df_import.columns:
                        df_final[col] = df_import[col]
                
                df_final = df_final.fillna("")
                
                name_import = f"saida_importacao/Importacao_ERP_{timestamp}.xlsx"
                df_final.to_excel(name_import, index=False)
                
                self.log_message(f"✅ [IMPORTAÇÃO] Arquivo gerado: {name_import}")
                self.log_message(f"   Total de linhas válidas: {len(df_final)}")
            else:
                self.log_message("⚠️  Nenhum pedido válido foi gerado para importação")
            
            self.log_message("")
            
            # 2. GERAR RELATÓRIO DE AUDITORIA (REJEITADOS)
            if rejected_data:
                self.log_message("✏️  Gerando relatório de auditoria...")
                df_audit = pd.DataFrame(rejected_data)
                name_audit = f"saida_auditoria/Relatorio_Auditoria_Rejeitados_{timestamp}.xlsx"
                df_audit.to_excel(name_audit, index=False)
                
                self.log_message(f"🛡️  [AUDITORIA] Arquivo gerado: {name_audit}")
                self.log_message(f"   Total de arquivos rejeitados: {len(df_audit)}")
            else:
                self.log_message("✅ Nenhum arquivo foi rejeitado!")
            
            # Resumo final
            self.log_message("")
            self.log_message("=" * 70)
            self.log_message("🎉 PROCESSAMENTO CONCLUÍDO COM SUCESSO!")
            self.log_message("=" * 70)
            self.log_message("")
            self.log_message("📂 Próximos passos:")
            self.log_message("   1. Clique em 'Abrir Resultado' para ver os arquivos gerados")
            self.log_message("   2. Importe os dados válidos no seu sistema")
            self.log_message("   3. Revise os rejeitados se necessário")
            
            if self.window:
                self.window['STATUS_TEXT'].update("✅ Processamento concluído!", text_color='lightgreen')
        
        except Exception as e:
            self.log_message(f"❌ ERRO: {str(e)}")
            self.log_message("Verifique se os arquivos Excel estão no diretório correto:")
            self.log_message("  - mapeamento_teknisa.xlsx")
            self.log_message("  - Relatorio potes.xlsx")
            if self.window:
                self.window['STATUS_TEXT'].update("❌ Erro no processamento", text_color='red')
        
        finally:
            self.processing = False
    
    def open_results_folder(self):
        """Abre a pasta de resultados no Windows Explorer"""
        result_folder = os.path.abspath('saida_importacao')
        
        if os.path.exists(result_folder):
            try:
                # Windows: abre pasta no Explorer
                import subprocess
                subprocess.Popen(f'explorer /select,"{result_folder}"')
                self.log_message("📂 Abrindo pasta de resultados...")
            except Exception as e:
                self.log_message(f"⚠️  Não foi possível abrir a pasta: {e}")
        else:
            self.log_message("⚠️  Pasta de resultados não encontrada")
    
    def run(self):
        """
        Loop principal da aplicação
        Aguarda eventos do usuário e processa comandos
        """
        self.window = self.create_window()
        
        self.log_message("🚀 Bem-vindo à Automação de Pedidos em PDF!")
        self.log_message("")
        self.log_message("📌 Como usar:")
        self.log_message("   1. Clique em '📂 Selecionar Pasta'")
        self.log_message("   2. Escolha a pasta onde estão seus PDFs")
        self.log_message("   3. Clique em '🚀 PROCESSAR'")
        self.log_message("   4. Aguarde a conclusão")
        self.log_message("   5. Clique em '📂 Abrir Resultado' para ver os arquivos")
        self.log_message("")
        self.log_message("=" * 70)
        
        while True:
            event, values = self.window.read(timeout=100)
            
            if event in ('EXIT', sg.WINDOW_CLOSED):
                self.log_message("👋 Encerrando aplicação...")
                break
            
            # Botão: Selecionar Pasta
            elif event == 'BROWSE':
                self.selected_folder = values.get('FOLDER')
                if self.selected_folder:
                    self.log_message(f"✅ Pasta selecionada: {self.selected_folder}")
                    self.window['STATUS_TEXT'].update("Pronto para processar", text_color='lightgreen')
            
            # Botão: Processar
            elif event == 'PROCESS':
                if not self.selected_folder or not values.get('FOLDER'):
                    sg.popup_error('⚠️  Selecione uma pasta de PDFs primeiro!')
                    continue
                
                if self.processing:
                    sg.popup_warning('⏳ Processamento já está em andamento...')
                    continue
                
                # Limpa log anterior
                self.window['LOG'].update('')
                self.update_progress(0)
                self.window['STATUS_TEXT'].update("Processando...", text_color='yellow')
                
                # Processa em thread separada (não congela interface)
                folder = values['FOLDER']
                thread = threading.Thread(target=self.process_folder, args=(folder,))
                thread.daemon = True
                thread.start()
            
            # Botão: Abrir Resultado
            elif event == 'OPEN_RESULT':
                self.open_results_folder()
        
        self.window.close()
        print("✅ Aplicação encerrada")


def main():
    """Função principal - inicia a aplicação"""
    try:
        app = GUIApp()
        app.run()
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        sg.popup_error(f"Erro: {e}")


if __name__ == '__main__':
    main()
