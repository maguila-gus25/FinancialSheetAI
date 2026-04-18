# FinancialSheetAI

AI reads your Bank statement, and gives a sheet of your life costs.

Sistema de gestão financeira pessoal que processa extratos bancários em PDF, utiliza inteligência artificial (Google Gemini) para extrair e categorizar transações automaticamente, e envia os dados para um webhook n8n que alimenta o Google Sheets.

## 🚀 Funcionalidades

- ✅ Processamento de extratos bancários em PDF (Santander, C6, BTG)
- ✅ **Suporte a PDFs criptografados** com senha configurável
- ✅ Extração automática de transações usando Google Gemini AI
- ✅ **Seleção de modelos Gemini** (gemini-2.5-flash, gemini-2.5-pro, etc.)
- ✅ Categorização automática em 14 categorias predefinidas
- ✅ Identificação automática do banco de origem
- ✅ Upload múltiplos PDFs simultaneamente
- ✅ Integração com n8n via webhook
- ✅ Interface web simples e intuitiva com Streamlit
- ✅ Sistema de logs para tratamento de erros
- ✅ Fallback automático de modelos em caso de indisponibilidade

## 📋 Pré-requisitos

- Python 3.8 ou superior
- Conta Google com acesso à API Gemini
- Webhook n8n configurado
- Google Sheets configurado para receber dados do n8n

## 🔧 Instalação

1. **Clone o repositório:**
```bash
git clone <seu-repositorio>
cd FinancialSheetAI
```

2. **Instale as dependências:**
```bash
pip install -r requirements.txt
```

3. **Configure as variáveis de ambiente:**
   - Crie um arquivo `.env` na raiz do projeto
   - Adicione suas credenciais:
```env
GOOGLE_API_KEY=sua_chave_google_gemini_aqui
N8N_WEBHOOK_URL=https://seu-webhook-n8n.com/webhook
```

4. **Obtenha sua chave da API Google Gemini:**
   - Acesse [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Crie uma nova API key
   - Copie e cole no arquivo `.env`

## 🎯 Como Usar

1. **Inicie a aplicação:**
```bash
streamlit run app.py
```

2. **Acesse a interface:**
   - Abra seu navegador em `http://localhost:8501`

3. **Configure as opções (sidebar):**
   - **Senha do PDF**: Se seus PDFs estiverem criptografados, configure a senha (padrão: 079984)
   - **Modelo Gemini**: Escolha o modelo de IA (recomendado: gemini-2.5-flash)

4. **Faça upload dos PDFs:**
   - Clique em "Browse files" ou arraste os arquivos PDF
   - Você pode selecionar múltiplos arquivos simultaneamente
   - **Nota**: PDFs criptografados serão automaticamente descriptografados usando a senha configurada

5. **Processe os extratos:**
   - Clique no botão "🚀 Processar Extratos"
   - Aguarde o processamento (pode levar alguns segundos por arquivo)

6. **Visualize os resultados:**
   - As transações serão automaticamente enviadas para o n8n
   - Verifique o Google Sheets para ver os dados atualizados
   - Visualize um preview das transações na interface antes do envio

## 📊 Estrutura do Google Sheets

Configure as seguintes colunas no seu Google Sheets para que o n8n possa mapear corretamente:

| Coluna | Tipo | Formato | Descrição |
|--------|------|---------|-----------|
| **Data** | Data/Texto | DD/MM/AAAA | Data da transação |
| **Descrição** | Texto | - | Descrição completa da transação |
| **Valor** | Número | Decimal | Valor da transação (positivo para entradas, negativo para saídas) |
| **Categoria** | Texto | - | Categoria da transação (ver lista abaixo) |
| **Banco** | Texto | - | Banco de origem (Santander, C6, BTG) |

### Categorias Disponíveis

As transações são automaticamente categorizadas em uma das seguintes categorias:

- Alimentação
- Educação
- Lazer
- Festas
- Transporte
- Gasolina
- Supermercado
- Presentes
- Habitação
- Contas Fixas
- Saúde
- Investimentos
- Assinaturas
- Outros

## 🔍 Identificação de Bancos

O sistema identifica automaticamente o banco de origem através de:

1. **Análise do conteúdo do PDF** (busca por palavras-chave como "Santander", "C6 Bank", "BTG Pactual")
2. **Análise do nome do arquivo** (fallback caso não encontre no conteúdo)
3. **"Desconhecido"** se não conseguir identificar

## 🔐 PDFs Criptografados

O sistema suporta PDFs protegidos por senha:

- **Senha padrão**: 079984 (configurável na sidebar)
- **Configuração**: Acesse a sidebar → "🔐 Configurações PDF" → "Senha do PDF"
- **Processamento automático**: PDFs criptografados são automaticamente descriptografados durante o processamento
- **Segurança**: A senha é usada apenas localmente e nunca é enviada para APIs externas

## 📤 Formato de Dados Enviados ao n8n

O webhook recebe um payload JSON no seguinte formato:

```json
{
  "banco_origem": "Santander|C6|BTG|Múltiplos",
  "transacoes": [
    {
      "data": "01/12/2024",
      "descricao": "COMPRA CARTAO - MERCADO XYZ",
      "valor": -150.50,
      "categoria": "Supermercado"
    }
  ]
}
```

## 🤖 Modelos Gemini Disponíveis

O sistema suporta múltiplos modelos do Google Gemini:

- **models/gemini-2.5-flash** (recomendado) - Mais rápido e eficiente
- **models/gemini-2.5-pro** - Mais preciso, ideal para documentos complexos
- **models/gemini-2.0-flash** - Versão anterior, ainda compatível
- **models/gemini-flash-latest** - Sempre usa a versão mais recente do Flash
- **models/gemini-pro-latest** - Sempre usa a versão mais recente do Pro

**Nota**: Se um modelo não estiver disponível, o sistema automaticamente tenta modelos alternativos (fallback).

## 🛠️ Estrutura do Projeto

```
FinancialSheetAI/
├── app.py                 # Aplicação principal Streamlit
├── requirements.txt       # Dependências Python
├── .env                   # Variáveis de ambiente (não versionado)
├── env_template.txt       # Template de variáveis de ambiente
├── .gitignore            # Arquivos ignorados pelo Git
├── venv/                 # Ambiente virtual Python (não versionado)
├── logs/                 # Diretório de logs de erros
│   └── errors_YYYY-MM-DD.log
└── README.md             # Este arquivo
```

## 🐛 Tratamento de Erros

- Erros são automaticamente registrados em arquivos de log em `logs/errors_YYYY-MM-DD.log`
- Erros também são exibidos na interface Streamlit
- Se uma transação não puder ser processada, ela é ignorada e o processamento continua

## 📝 Logs

Os logs de erro são salvos automaticamente em:
- `logs/errors_YYYY-MM-DD.log`

Cada entrada de log contém:
- Timestamp
- Nome do arquivo PDF
- Mensagem de erro
- Detalhes adicionais

## 🔒 Segurança

- ⚠️ **Nunca commite o arquivo `.env`** com suas credenciais
- Use `.env.example` como template
- Mantenha suas chaves de API seguras

## 📚 Dependências Principais

- `streamlit` - Interface web
- `PyMuPDF` (fitz) - Extração de texto de PDFs
- `google-generativeai` - Integração com Google Gemini API
- `python-dotenv` - Gerenciamento de variáveis de ambiente
- `requests` - Requisições HTTP para webhook n8n
- `python-dateutil` - Validação de datas

## 🤝 Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou pull requests.

## 📄 Licença

Este projeto é de uso pessoal.

## 🆘 Suporte

Se encontrar problemas:

1. **Erro de modelo não encontrado**: 
   - Selecione `models/gemini-2.5-flash` ou `models/gemini-pro-latest` na sidebar
   - O sistema tentará automaticamente modelos alternativos

2. **Erro ao abrir PDF criptografado**:
   - Verifique se a senha está correta na sidebar
   - A senha padrão é 079984, mas pode ser alterada

3. **Outros problemas**:
   - Verifique se todas as variáveis de ambiente estão configuradas corretamente
   - Verifique os logs em `logs/errors_YYYY-MM-DD.log`
   - Certifique-se de que o PDF contém texto extraível (não é apenas imagem)
   - Verifique se a API key do Google Gemini está válida e com créditos disponíveis
