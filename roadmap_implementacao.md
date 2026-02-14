# 🛠️ ROADMAP DE IMPLEMENTAÇÃO - DETALHADO

**Status:** Aguardando confirmação dos arquivos Excel  
**Próximas ações:** Implementação imediata após confirmação

---

## 📂 ESTRUTURA DE ARQUIVOS FINAL

```
AutomacaoPedidos/
│
├── 📄 app.exe ← NOVO (executável pronto)
├── 📄 app.py ← NOVO (GUI principal)
│
├── 📄 main.py (MODIFICADO - mantém compatibilidade)
├── 📄 processor.py (CORRIGIDO - 3 bugs resolvidos)
├── 📄 config.py (SEM MUDANÇAS)
│
├── 📁 entrada_pdfs/ (pasta para PDFs do usuário)
├── 📁 saida_importacao/ (Excel com pedidos válidos)
├── 📁 saida_auditoria/ (Excel com rejeitados)
│
├── 📄 requirements.txt
├── 📄 README.txt ← NOVO (instruções de uso)
│
├── 📄 mapeamento_teknisa.xlsx (seu arquivo)
└── 📄 Relatorio potes.xlsx (seu arquivo)
```

---

## 📝 RESUMO DAS MODIFICAÇÕES

| Arquivo | Status | O que muda | Por quê |
|---------|--------|-----------|---------|
| **app.py** | ✨ NOVO | Interface PySimpleGUI | Solicitar pelo usuário |
| **processor.py** | 🔧 CORRIGIDO | Bug #1, #2, #3 resolvidos | Melhorias críticas |
| **main.py** | ✏️ MODIFICADO | Adiciona modo GUI | Compatibilidade |
| **config.py** | ✅ SEM MUDANÇA | Mantém como está | Funciona perfeitamente |
| **requirements.txt** | ✏️ MODIFICADO | Adiciona PySimpleGUI | Necessário para GUI |

---

## 🔧 MODIFICAÇÃO #1: processor.py

### BUG #1 - CNPJ Duplicado (Linhas 112-153)

**ANTES:**
```python
def validate_fiscal_client(self, full_text):
    """Problema: Busca TODOS os CNPJs, rejeita se tiver 2+"""
    
    regex_formatted = r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}'
    matches = re.findall(regex_formatted, full_text)
    
    candidates = set()
    for m in matches:
        clean_cnpj = re.sub(r'\D', '', m)
        candidates.add(clean_cnpj)  # ❌ TODOS
    
    valid_candidates = [c for c in candidates if c in self.data_manager.valid_cnpjs]
    
    if len(valid_candidates) > 1:
        return None, "REJEITADO: Ambiguidade Fiscal"  # ❌ REJEITA
```

**DEPOIS:**
```python
def validate_fiscal_client(self, full_text):
    """Solução: Procura especificamente o DESTINATÁRIO/CLIENTE"""
    
    # 1. Tentar padrão prioritário: "DESTINATARIO:" ou "CLIENTE:"
    destinatario_pattern = r'(?:DESTINATARIO|CLIENTE)[:\s]*[A-Z\s]*?(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})'
    match_dest = re.search(destinatario_pattern, full_text, re.IGNORECASE)
    
    candidates = set()
    
    if match_dest:
        # ✅ Encontrou CNPJ após DESTINATÁRIO → usar este
        clean_cnpj = re.sub(r'\D', '', match_dest.group(1))
        if len(set(clean_cnpj)) > 1:  # Validação extra
            candidates.add(clean_cnpj)
    
    # 2. Se não encontrou, tentar fallback: primeiro CNPJ válido
    if not candidates:
        regex_formatted = r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}'
        matches = re.findall(regex_formatted, full_text)
        
        for m in matches:
            clean_cnpj = re.sub(r'\D', '', m)
            if clean_cnpj in self.data_manager.valid_cnpjs:
                candidates.add(clean_cnpj)
                break  # ✅ Apenas o PRIMEIRO válido
    
    # 3. Retornar com prioridade
    if candidates:
        return list(candidates)[0], "VALIDADO"
    else:
        return None, "CNPJ não encontrado ou não validado"
```

**Resultado:**
```
❌ Antes: Rejeita por ambiguidade
✅ Depois: Aceita o CNPJ do DESTINATÁRIO correto
```

---

### BUG #2 - Layouts Diferentes (Linhas 195-261)

**NOVO MÉTODO: Detecção de Layout**

```python
def detect_layout_type(self, full_text):
    """
    Detecta qual layout o PDF segue baseado em markers
    Retorna: 'FREDDO' | 'CONDOR' | 'GENERICO'
    """
    text_upper = full_text.upper()
    
    # Markers específicos
    is_freddo = ("GIASSI" in text_upper and "VIAREGGIO" in text_upper) or \
                "DESCRICAO DA MERCADORIA" in text_upper
    
    is_condor = "CONDOR SUPER CENTER" in text_upper or \
                ("Produto" in text_upper and "Preco IPI" in text_upper)
    
    if is_freddo:
        return "FREDDO"
    elif is_condor:
        return "CONDOR"
    else:
        return "GENERICO"
```

**NOVOS MÉTODOS: Extração por Layout**

```python
def extract_products_by_layout(self, page, layout_type, id_cliente):
    """Delega para função específica conforme layout"""
    
    if layout_type == "FREDDO":
        return self.extract_products_freddo(page, id_cliente)
    elif layout_type == "CONDOR":
        return self.extract_products_condor(page, id_cliente)
    else:
        return self.extract_products_generic(page, id_cliente)

def extract_products_freddo(self, page, id_cliente):
    """
    Layout FREDDO:
    - Tabela em cascata
    - Produto, Código, Quantidade na mesma linha
    - Código em coluna "Cod/Ean/Dun14"
    """
    words = page.extract_words(x_tolerance=3, y_tolerance=3)
    extracted = []
    
    # Lógica específica para layout FREDDO
    # (detalhado abaixo)
    
    return extracted

def extract_products_condor(self, page, id_cliente):
    """
    Layout CONDOR:
    - Código do produto em linha separada
    - Quantidade em coluna "Qtde"
    - Formatação mais espaçada
    """
    words = page.extract_words(x_tolerance=3, y_tolerance=3)
    extracted = []
    
    # Lógica específica para layout CONDOR
    # (detalhado abaixo)
    
    return extracted

def extract_products_generic(self, page, id_cliente):
    """Fallback: lógica genérica original (aprimorada)"""
    # ... código existente melhorado
```

---

### BUG #3 - Quantidade Errada (Linhas 234-253)

**ANTES:**
```python
# Procura qualquer número à direita do produto
# Problema: Pega número errado (preço, CNPJ, etc)
candidates = []
for w in line_words:
    clean_w = re.sub(r'\D', '', w['text'])
    if clean_w:
        val = int(clean_w)
        if val < 5000:  # ← Filtro fraco demais
            candidates.append({'val': val, 'x': w['x0']})
```

**DEPOIS:**
```python
# Busca quantidade com contexto melhor
candidates = []
for w in line_words:
    clean_w = re.sub(r'\D', '', w['text'])
    if not clean_w:
        continue
    
    val = int(clean_w)
    
    # Filtros mais rigorosos:
    if str(val) in str(product_id):
        continue  # É parte do ID
    if str(val) in id_cliente:
        continue  # É parte do CNPJ
    if val == 0:
        continue  # Zero não é quantidade
    if val > 10000:
        continue  # Quantidade impossível
    if val < 1:
        continue  # Deve ser >= 1
    
    # ✅ Agora só valores plausíveis
    candidates.append({'val': val, 'x': w['x0']})

if candidates:
    # Pega quantidade mais próxima ao produto (melhor heurística)
    best_candidate = min(candidates, key=lambda c: abs(c['x'] - product_x))
    qtd_final = best_candidate['val']
```

---

## ✨ NOVO ARQUIVO: app.py (GUI com PySimpleGUI)

### Estrutura:

```python
import PySimpleGUI as sg
from processor import PDFProcessor
from config import DataManager
import os
import glob
from datetime import datetime

class GUIApp:
    def __init__(self):
        sg.theme('DarkBlue2')  # Tema visual
        self.processor = PDFProcessor()
        self.selected_folder = None
        self.run()
    
    def create_window(self):
        """Cria interface gráfica"""
        layout = [
            [sg.Text('🎯 AUTOMAÇÃO DE PEDIDOS EM PDF', 
                    font=('Arial', 16, 'bold'))],
            
            [sg.HorizontalSeparator()],
            
            # Seleção de pasta
            [sg.Text('📁 Pasta de PDFs:'),
             sg.InputText(key='FOLDER', size=(40, 1), disabled=True),
             sg.FolderBrowse('Selecionar', key='BROWSE')],
            
            # Área de status
            [sg.Multiline(size=(60, 15), key='LOG', disabled=True)],
            
            # Botões
            [sg.Button('🚀 Processar', key='PROCESS'),
             sg.Button('📂 Abrir Resultado', key='OPEN_RESULT'),
             sg.Button('❌ Sair', key='EXIT')]
        ]
        
        return sg.Window('Automação de Pedidos', layout)
    
    def process_folder(self, folder_path):
        """Processa todos os PDFs da pasta"""
        pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))
        
        log_text = f"Encontrados {len(pdf_files)} arquivos\n\n"
        valid_count = 0
        rejected_count = 0
        
        for pdf_path in pdf_files:
            filename = os.path.basename(pdf_path)
            log_text += f"Processando: {filename}...\n"
            
            result = self.processor.process_pdf(pdf_path, filename)
            
            if result['status'] == 'SUCESSO':
                log_text += f"  ✅ ACEITO: {len(result['itens'])} linhas\n"
                valid_count += 1
            else:
                log_text += f"  ❌ REJEITADO: {result['motivo']}\n"
                rejected_count += 1
        
        log_text += f"\n{'='*60}\n"
        log_text += f"Processamento Concluído\n"
        log_text += f"✅ Válidos: {valid_count}\n"
        log_text += f"❌ Rejeitados: {rejected_count}\n"
        
        return log_text
    
    def run(self):
        """Loop principal da GUI"""
        window = self.create_window()
        
        while True:
            event, values = window.read()
            
            if event in ('EXIT', sg.WINDOW_CLOSED):
                break
            
            elif event == 'BROWSE':
                self.selected_folder = values.get('FOLDER')
            
            elif event == 'PROCESS':
                if not self.selected_folder:
                    sg.popup_error('Selecione uma pasta primeiro!')
                    continue
                
                log = self.process_folder(self.selected_folder)
                window['LOG'].update(log)
            
            elif event == 'OPEN_RESULT':
                result_folder = 'saida_importacao'
                if os.path.exists(result_folder):
                    os.startfile(result_folder)  # Windows Explorer
        
        window.close()

if __name__ == '__main__':
    app = GUIApp()
```

**Resultado Visual:**
```
╔════════════════════════════════════════════════════╗
║ 🎯 AUTOMAÇÃO DE PEDIDOS EM PDF                    ║
╠════════════════════════════════════════════════════╣
║ 📁 Pasta de PDFs:                                  ║
║ [C:\Users\...\entrada_pdfs] [Selecionar]          ║
║                                                    ║
║ Processando: FREDDO_28_01.pdf...                  ║
║   ✅ ACEITO: 18 linhas                            ║
║ Processando: Pedido_9205753.pdf...                ║
║   ✅ ACEITO: 8 linhas                             ║
║                                                    ║
║ ════════════════════════════════════════════════  ║
║ Processamento Concluído                           ║
║ ✅ Válidos: 2                                      ║
║ ❌ Rejeitados: 0                                   ║
║                                                    ║
║ [🚀 Processar] [📂 Abrir Resultado] [❌ Sair]    ║
╚════════════════════════════════════════════════════╝
```

---

## 📄 NOVO ARQUIVO: README.txt

```
╔═════════════════════════════════════════════════════════════╗
║        AUTOMAÇÃO DE PEDIDOS EM PDF - GUIA DE USO           ║
╚═════════════════════════════════════════════════════════════╝

🚀 COMO USAR:

1. Clique em app.exe
2. Clique em "Selecionar"
3. Escolha a pasta onde estão seus PDFs
4. Clique em "Processar"
5. Aguarde... (normalmente 5-30 segundos)
6. Clique em "Abrir Resultado"

📂 PASTAS:

entrada_pdfs/
  └─ Coloque seus PDFs aqui
     (Ex: FREDDO_28_01.pdf, Pedido_9205753.pdf)

saida_importacao/
  └─ Excel com pedidos VÁLIDOS
     Importar no ERP/Sistema

saida_auditoria/
  └─ Excel com pedidos REJEITADOS
     Revisar motivo da rejeição

📋 SIGNIFICADO DOS STATUS:

✅ ACEITO
   Pedido foi processado com sucesso
   → Vai para saida_importacao/

❌ REJEITADO
   Erro na validação
   → Vai para saida_auditoria/
   → Verifique o motivo (CNPJ inválido, etc)

🔧 TROUBLESHOOTING:

Problema: "Nenhum CNPJ encontrado"
Solução: Verifique se o PDF tem CNPJ válido

Problema: "Múltiplos CNPJs encontrados"
Solução: PDF com CNPJs não cadastrados

Problema: "Nenhum produto identificado"
Solução: Verifique se produto está na base

📞 SUPORTE:

Dúvidas sobre o funcionamento?
Verifique o arquivo de log: processamento_pedidos.log

Quer adicionar novos PDFs?
1. Coloque na pasta entrada_pdfs/
2. Execute novamente
3. Sistema processa automaticamente

═════════════════════════════════════════════════════════════
Versão: 1.0 | Data: 14/02/2026
```

---

## 🎁 ARQUIVO GERADO: requirements.txt

```
pandas==2.2.0
openpyxl==3.1.2
pdfplumber==0.10.3
pytesseract==0.3.10
rapidfuzz==3.6.1
unidecode==1.3.8
Pillow==10.2.0
PySimpleGUI==4.60.5
PyInstaller==6.1.0
```

---

## 🔨 PASSO-A-PASSO DE GERAÇÃO DO .EXE

Após finalizar código, vou gerar o executável:

```bash
# 1. Instalar PyInstaller
pip install PyInstaller

# 2. Gerar executável (one-file, windowed)
pyinstaller --onefile --windowed --name="AutomacaoPedidos" app.py

# 3. Resultado em: dist/AutomacaoPedidos.exe
```

O .exe será:
- ✅ Standalone (não precisa Python)
- ✅ ~60MB de tamanho
- ✅ Funciona offline
- ✅ Clique duplo para abrir

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

- [ ] **FASE 1: Correção de processor.py**
  - [ ] Bug #1: validate_fiscal_client (CNPJ)
  - [ ] Bug #2: detect_layout_type + 3 funções
  - [ ] Bug #3: Filtro de quantidade
  - [ ] Testes com PDFs fornecidos

- [ ] **FASE 2: Criar app.py (GUI)**
  - [ ] Classe GUIApp com PySimpleGUI
  - [ ] Integração com processor.py
  - [ ] Logs visuais em tempo real
  - [ ] Botões funcionando

- [ ] **FASE 3: Arquivos de suporte**
  - [ ] README.txt
  - [ ] requirements.txt atualizado
  - [ ] main.py mantém compatibilidade

- [ ] **FASE 4: Geração do .exe**
  - [ ] PyInstaller configurado
  - [ ] Testes end-to-end
  - [ ] Documentação final

---

## 🎯 PRÓXIMAS AÇÕES

1. ✅ Você responde as 2 perguntas sobre arquivos Excel
2. 📝 Eu implemento o código corrigido
3. 🧪 Você testa com PDFs reais
4. 📦 Eu gero o executável
5. 🎉 Solução pronta para usar

**Tempo estimado: 2-3 dias úteis**

---

Assim que você confirmar os arquivos Excel, começo a implementação! 🚀
