╔═════════════════════════════════════════════════════════════════╗
║                                                                 ║
║        AUTOMAÇÃO DE PEDIDOS EM PDF - GUIA DE USO v1.0          ║
║                                                                 ║
║        Data: 14/02/2026                                         ║
║        Desenvolvido para processamento de PDFs fiscais          ║
║                                                                 ║
╚═════════════════════════════════════════════════════════════════╝


🎯 COMO USAR (INTERFACE GRÁFICA)
═════════════════════════════════════════════════════════════════

Passo 1: ABRA O PROGRAMA
   └─ Clique em "AutomacaoPedidos.exe" (duplo clique)
   └─ A interface gráfica aparecerá em segundos

Passo 2: SELECIONE OS ARQUIVOS
   └─ Clique no botão "📂 Selecionar Pasta"
   └─ Navegue até a pasta onde estão seus PDFs
   └─ Clique em "Selecionar Pasta"

Passo 3: PROCESSE OS PDFS
   └─ Clique no botão "🚀 PROCESSAR"
   └─ Aguarde (normalmente 5-30 segundos)
   └─ O status será mostrado em tempo real

Passo 4: VEJA OS RESULTADOS
   └─ Clique em "📂 Abrir Resultado"
   └─ Dois arquivos Excel serão gerados:
      ✅ Importacao_ERP_*.xlsx (pedidos válidos)
      ❌ Relatorio_Auditoria_Rejeitados_*.xlsx (problemas)


📂 ESTRUTURA DE PASTAS
═════════════════════════════════════════════════════════════════

AutomacaoPedidos/
│
├── 📄 AutomacaoPedidos.exe ← CLIQUE AQUI PARA ABRIR
│
├── 📁 entrada_pdfs/
│   └─ Coloque seus PDFs aqui
│      Exemplo:
│      ├── FREDDO_28_01.pdf
│      ├── Pedido_9205753.pdf
│      └── outro_pedido.pdf
│
├── 📁 saida_importacao/
│   └─ Excel com PEDIDOS VÁLIDOS
│      Estes dados podem ser importados no ERP/Sistema
│      Arquivo: Importacao_ERP_YYYYMMDD_HHMMSS.xlsx
│
├── 📁 saida_auditoria/
│   └─ Excel com PEDIDOS REJEITADOS
│      Revise o motivo da rejeição
│      Arquivo: Relatorio_Auditoria_Rejeitados_YYYYMMDD_HHMMSS.xlsx
│
├── 📄 mapeamento_teknisa.xlsx (NECESSÁRIO)
│   └─ Whitelist de CNPJs válidos
│
├── 📄 Relatorio potes.xlsx (NECESSÁRIO)
│   └─ Catálogo de produtos
│
└── 📄 processamento_pedidos.log
    └─ Arquivo de log (técnico)


📋 SIGNIFICADO DOS STATUS
═════════════════════════════════════════════════════════════════

✅ ACEITO
   ├─ O PDF foi processado com sucesso
   ├─ CNPJ foi validado na whitelist
   ├─ Produtos foram identificados
   └─ Dados foram incluídos no arquivo de importação

❌ REJEITADO: CNPJ não encontrado
   ├─ O PDF não contém um CNPJ válido
   ├─ Ou o CNPJ não está na whitelist
   ├─ Ação: Verifique se o PDF tem CNPJ
   └─ Ação: Verifique se CNPJ está em mapeamento_teknisa.xlsx

❌ REJEITADO: Nenhum produto identificado
   ├─ O CNPJ foi validado
   ├─ Mas nenhum produto foi encontrado
   ├─ Ação: Verifique se produtos estão em Relatorio potes.xlsx
   └─ Ação: Verifique se código/nome está correto no PDF

❌ REJEITADO: Ambiguidade Fiscal
   ├─ Multiple CNPJs encontrados (que não deveriam estar)
   ├─ Ação: Verifique o layout do PDF
   └─ Ação: Entre em contato com suporte


🔧 TROUBLESHOOTING
═════════════════════════════════════════════════════════════════

PROBLEMA: "Arquivo não foi gerado"
SOLUÇÃO:
   1. Verifique se os arquivos Excel estão no diretório:
      ✓ mapeamento_teknisa.xlsx
      ✓ Relatorio potes.xlsx
   2. Verifique se a pasta 'entrada_pdfs' tem PDFs
   3. Tente novamente

PROBLEMA: "CNPJ não encontrado"
SOLUÇÃO:
   1. Abra o PDF e verifique se tem CNPJ
   2. Abra mapeamento_teknisa.xlsx
   3. Procure o CNPJ na coluna 'id_cliente_teknisa'
   4. Se não existir, adicione o CNPJ à whitelist

PROBLEMA: "Nenhum produto identificado"
SOLUÇÃO:
   1. Abra Relatorio potes.xlsx
   2. Procure o produto pela coluna 'Código' ou 'Nome do Produto'
   3. Se não encontrar, adicione o produto à base
   4. Use exatamente o mesmo nome que está no PDF

PROBLEMA: "Aplicação não abre"
SOLUÇÃO:
   1. Verifique se está em Windows (7, 10, 11)
   2. Tente atualizar Windows
   3. Tente fazer download novamente do arquivo .exe
   4. Entre em contato com suporte

PROBLEMA: "Tesseract não encontrado" (erro em log)
SOLUÇÃO:
   Este é um aviso (não impede funcionamento)
   A aplicação funciona mesmo sem Tesseract
   Ele é opcional para OCR em PDFs escaneados


💻 USO AVANÇADO (TERMINAL - MODO COMPATIBILIDADE)
═════════════════════════════════════════════════════════════════

Se preferir usar o modo terminal (sem interface gráfica):

1. Abra Prompt de Comando (cmd.exe)
2. Navegue até a pasta:
   cd C:\caminho\para\AutomacaoPedidos
3. Execute:
   python main.py

O sistema processará automaticamente todos os PDFs em 'entrada_pdfs'


📊 COLUNAS DO ARQUIVO DE IMPORTAÇÃO
═════════════════════════════════════════════════════════════════

Arquivo: Importacao_ERP_*.xlsx

Coluna 1: ID_Pedido
   └─ Identificação do pedido extraída do PDF

Coluna 2: ID_FilialDestino
   └─ Identificação da filial destino (de mapeamento_teknisa.xlsx)

Coluna 3: ID_Cliente
   └─ CNPJ do cliente (14 dígitos)

Coluna 4: ID_Produto
   └─ Código do produto (extraído do PDF)

Coluna 5: Quantidade
   └─ Quantidade de itens do produto


✨ MELHORIAS DA VERSÃO 1.0
═════════════════════════════════════════════════════════════════

✅ CORRIGIDO: Problema de CNPJ duplicado
   └─ Agora detecta corretamente qual é o cliente verdadeiro

✅ NOVO: Reconhecimento de múltiplos layouts
   └─ Suporta layouts FREDDO, CONDOR e genéricos

✅ NOVO: Interface gráfica (PySimpleGUI)
   └─ Sem necessidade de conhecimento técnico

✅ NOVO: Processamento em tempo real
   └─ Veja o progresso enquanto processa

✅ MELHORADO: Extração de quantidade
   └─ Filtros mais precisos para evitar números errados


🌍 SUPORTE E CONTATO
═════════════════════════════════════════════════════════════════

Se encontrar problemas:

1. Verifique o arquivo de log:
   └─ processamento_pedidos.log

2. Revise este README novamente (seção Troubleshooting)

3. Verifique se os arquivos Excel estão corretos:
   └─ mapeamento_teknisa.xlsx (DePara_Clientes)
   └─ Relatorio potes.xlsx

4. Se o problema persistir, entre em contato com o desenvolvedor


📝 NOTAS IMPORTANTES
═════════════════════════════════════════════════════════════════

• A aplicação foi testada com Windows 10 e 11
• Recomenda-se manter os arquivos Excel no mesmo diretório
• Certifique-se de que os PDFs estão em formato correto
• O arquivo de log pode ajudar na depuração (processamento_pedidos.log)
• Os arquivos gerados têm timestamp para evitar sobrescrita


🎉 VOCÊ ESTÁ PRONTO!
═════════════════════════════════════════════════════════════════

1. Clique em AutomacaoPedidos.exe
2. Selecione pasta com PDFs
3. Clique em "Processar"
4. Pronto! Seus dados foram extraídos automaticamente

Boa sorte! 🚀

═════════════════════════════════════════════════════════════════
Versão: 1.0 | Data: 14/02/2026
