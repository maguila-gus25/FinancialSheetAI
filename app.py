import streamlit as st
import fitz  # PyMuPDF
import google.generativeai as genai
import os
import json
import re
import requests
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# Carregar variáveis de ambiente
load_dotenv()

# Configuração da página Streamlit
st.set_page_config(
    page_title="Gestão Financeira - Processador de Extratos",
    page_icon="💰",
    layout="wide"
)

# Categorias permitidas
CATEGORIAS_PERMITIDAS = [
    "Alimentação", "Educação", "Lazer", "Festas", "Transporte",
    "Gasolina", "Supermercado", "Presentes", "Habitação", "Contas Fixas",
    "Saúde", "Investimentos", "Assinaturas", "Outros"
]

# Criar diretório de logs se não existir
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Senha padrão para PDFs criptografados
PDF_PASSWORD = "079984"


def extract_text_from_pdf(pdf_file, password=None):
    """
    Extrai texto de um arquivo PDF usando PyMuPDF.
    Suporta PDFs protegidos por senha.
    
    Args:
        pdf_file: Arquivo PDF carregado pelo Streamlit
        password: Senha do PDF (opcional, usa senha padrão se None)
        
    Returns:
        str: Texto extraído do PDF
    """
    # Usar senha padrão se não fornecida
    if password is None:
        password = PDF_PASSWORD
    
    try:
        # Ler o conteúdo do arquivo
        pdf_bytes = pdf_file.read()
        
        # Abrir o PDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # Verificar se está criptografado e autenticar se necessário
        if doc.is_encrypted:
            if not doc.authenticate(password):
                doc.close()
                raise Exception("Senha do PDF incorreta. Verifique se a senha está correta.")
        
        text = ""
        for page in doc:
            text += page.get_text()
        
        doc.close()
        return text
    except Exception as e:
        error_msg = str(e)
        if "password" in error_msg.lower() or "encrypted" in error_msg.lower() or "incorreta" in error_msg.lower():
            raise Exception(f"Erro ao abrir PDF protegido: {error_msg}")
        raise Exception(f"Erro ao extrair texto do PDF: {error_msg}")


def identify_bank(text, filename):
    """
    Identifica o banco pelo conteúdo do PDF ou nome do arquivo.
    
    Args:
        text: Texto extraído do PDF
        filename: Nome do arquivo PDF
        
    Returns:
        str: Nome do banco identificado
    """
    text_upper = text.upper()
    filename_upper = filename.upper()
    
    # Buscar no conteúdo do PDF
    if "SANTANDER" in text_upper:
        return "Santander"
    elif "C6" in text_upper or "C6 BANK" in text_upper or "C6BANK" in text_upper:
        return "C6"
    elif "BTG" in text_upper or "BTG PACTUAL" in text_upper or "BTGPACTUAL" in text_upper:
        return "BTG"
    
    # Fallback: buscar no nome do arquivo
    if "santander" in filename_upper:
        return "Santander"
    elif "c6" in filename_upper:
        return "C6"
    elif "btg" in filename_upper:
        return "BTG"
    
    return "Desconhecido"


def normalize_value(value_str):
    """
    Normaliza valores numéricos: converte vírgula em ponto e trata sinais negativos.
    
    Args:
        value_str: String com o valor (pode conter vírgula, pontos, sinais)
        
    Returns:
        float: Valor numérico normalizado
    """
    if isinstance(value_str, (int, float)):
        return float(value_str)
    
    # Remover espaços e caracteres especiais, exceto números, vírgula, ponto e sinal negativo
    value_str = str(value_str).strip()
    value_str = re.sub(r'[^\d,.\-]', '', value_str)
    
    # Verificar se é negativo (pode estar no início ou no final)
    is_negative = False
    if value_str.startswith('-') or value_str.endswith('-'):
        is_negative = True
        value_str = value_str.replace('-', '')
    
    # Substituir vírgula por ponto
    value_str = value_str.replace(',', '.')
    
    # Remover pontos extras (mantém apenas o último como decimal)
    parts = value_str.split('.')
    if len(parts) > 2:
        # Múltiplos pontos - assumir que o último é decimal
        value_str = ''.join(parts[:-1]) + '.' + parts[-1]
    
    try:
        value = float(value_str)
        return -value if is_negative else value
    except ValueError:
        raise ValueError(f"Não foi possível converter '{value_str}' para número")


def call_gemini_api(text, bank_name, model_name="models/gemini-2.5-flash"):
    """
    Chama a API do Google Gemini para extrair e categorizar transações.
    
    Args:
        text: Texto extraído do PDF
        bank_name: Nome do banco identificado
        model_name: Nome do modelo Gemini a usar (padrão: models/gemini-2.5-flash)
        
    Returns:
        str: Resposta JSON da API
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise Exception("GOOGLE_API_KEY não encontrada nas variáveis de ambiente")
    
    genai.configure(api_key=api_key)
    
    # Tentar usar o modelo especificado, com fallback para modelos alternativos
    fallback_models = [
        "models/gemini-2.5-flash",
        "models/gemini-2.0-flash",
        "models/gemini-flash-latest",
        "models/gemini-pro-latest"
    ]
    
    model = None
    last_error = None
    
    # Tentar o modelo especificado primeiro
    try:
        model = genai.GenerativeModel(model_name)
    except Exception as e:
        last_error = str(e)
        # Tentar modelos de fallback
        for fallback in fallback_models:
            if fallback != model_name:
                try:
                    model = genai.GenerativeModel(fallback)
                    break
                except Exception:
                    continue
    
    if model is None:
        raise Exception(f"Erro ao configurar modelo Gemini. Nenhum modelo disponível funcionou. Último erro: {last_error}. Verifique se sua API key está correta e tem acesso aos modelos.")
    
    # Prompt melhorado para faturas de cartão de crédito
    bank_specific_instructions = ""
    if bank_name == "C6":
        bank_specific_instructions = """
INSTRUÇÕES ESPECÍFICAS PARA C6 BANK:
- Procure por seções como "Compras nacionais", "Compras internacionais", "Resumo da fatura"
- Transações podem aparecer em formato de lista com data, descrição e valor
- Valores de compras no cartão são sempre negativos (saídas)
- Pagamentos e estornos são positivos (entradas)
- Ignore valores de resumo, totais, limites e encargos - apenas transações individuais
"""
    
    prompt = f"""Você é um especialista em análise de extratos bancários e faturas de cartão de crédito.

Sua tarefa é extrair TODAS as transações financeiras individuais do documento abaixo.
{bank_specific_instructions}

Para cada transação encontrada, identifique:
1. Data: formato DD/MM/AAAA (se não houver data específica, use a data de fechamento da fatura)
2. Descrição: texto completo e descritivo da transação (ex: "COMPRA CARTAO - MERCADO XYZ", "PAGAMENTO FATURA")
3. Valor: número decimal (positivo para entradas/depósitos/estornos, negativo para saídas/compras/pagamentos)
4. Categoria: uma das categorias obrigatórias: {', '.join(CATEGORIAS_PERMITIDAS)}

REGRAS IMPORTANTES:
- Retorne APENAS um JSON válido, sem texto adicional, explicações ou markdown
- Formato exato: [{{"data": "DD/MM/AAAA", "descricao": "...", "valor": -150.50, "categoria": "Supermercado"}}]
- Valores de compras/pagamentos são NEGATIVOS (ex: -150.50)
- Valores de depósitos/estornos são POSITIVOS (ex: 150.50)
- Se NÃO encontrar nenhuma transação individual, retorne: []
- NÃO inclua totais, resumos, limites ou valores agregados - apenas transações individuais
- Categorize baseado na descrição: "MERCADO" → Supermercado, "POSTO" → Gasolina, "UBER" → Transporte, etc.

Texto do extrato:
{text[:50000]}"""  # Limitar a 50000 caracteres para evitar exceder limites da API
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        raise Exception(f"Erro ao chamar API Gemini: {str(e)}")


def parse_gemini_response(response_text):
    """
    Valida e parseia a resposta JSON da Gemini.
    
    Args:
        response_text: Texto retornado pela API Gemini
        
    Returns:
        list: Lista de transações parseadas e validadas
    """
    try:
        # Limpar o texto - remover markdown code blocks se existirem
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        elif cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        cleaned_text = cleaned_text.strip()
        
        # Parsear JSON
        transactions = json.loads(cleaned_text)
        
        if not isinstance(transactions, list):
            raise ValueError("Resposta não é uma lista")
        
        # Validar e normalizar cada transação
        validated_transactions = []
        for trans in transactions:
            if not isinstance(trans, dict):
                continue
            
            # Validar campos obrigatórios
            if "data" not in trans or "descricao" not in trans or "valor" not in trans or "categoria" not in trans:
                continue
            
            # Validar formato de data (DD/MM/AAAA)
            date_pattern = r'^\d{2}/\d{2}/\d{4}$'
            if not re.match(date_pattern, trans["data"]):
                continue
            
            # Validar categoria
            if trans["categoria"] not in CATEGORIAS_PERMITIDAS:
                trans["categoria"] = "Outros"
            
            # Normalizar valor
            try:
                trans["valor"] = normalize_value(trans["valor"])
            except ValueError:
                continue
            
            # Validar descrição
            if not trans["descricao"] or len(trans["descricao"].strip()) == 0:
                continue
            
            validated_transactions.append({
                "data": trans["data"],
                "descricao": trans["descricao"].strip(),
                "valor": trans["valor"],
                "categoria": trans["categoria"]
            })
        
        return validated_transactions
    except json.JSONDecodeError as e:
        raise ValueError(f"Erro ao parsear JSON: {str(e)}")
    except Exception as e:
        raise ValueError(f"Erro ao processar resposta: {str(e)}")


def send_to_n8n(transactions, bank_name):
    """
    Envia transações para o webhook do n8n.
    
    Args:
        transactions: Lista de transações
        bank_name: Nome do banco
        
    Returns:
        dict: Resposta da requisição
    """
    webhook_url = os.getenv("N8N_WEBHOOK_URL")
    if not webhook_url:
        raise Exception("N8N_WEBHOOK_URL não encontrada nas variáveis de ambiente")
    
    payload = {
        "banco_origem": bank_name,
        "transacoes": transactions
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
        return {"status": "success", "response": response.json() if response.content else None}
    except requests.exceptions.RequestException as e:
        raise Exception(f"Erro ao enviar para n8n: {str(e)}")


def save_error_log(error, pdf_name, details=""):
    """
    Salva erros em arquivo de log.
    
    Args:
        error: Mensagem de erro
        pdf_name: Nome do arquivo PDF que causou o erro
        details: Detalhes adicionais do erro
    """
    log_file = LOG_DIR / f"errors_{datetime.now().strftime('%Y-%m-%d')}.log"
    
    log_entry = f"""
[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]
PDF: {pdf_name}
Erro: {error}
Detalhes: {details}
{'='*80}
"""
    
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass  # Se não conseguir salvar o log, não quebrar a aplicação


# Interface Streamlit
def main():
    st.title("💰 Processador de Extratos Bancários")
    st.markdown("---")
    
    # Verificar variáveis de ambiente
    if not os.getenv("GOOGLE_API_KEY"):
        st.error("⚠️ GOOGLE_API_KEY não configurada. Configure no arquivo .env")
        st.stop()
    
    if not os.getenv("N8N_WEBHOOK_URL"):
        st.error("⚠️ N8N_WEBHOOK_URL não configurada. Configure no arquivo .env")
        st.stop()
    
    # Configuração da senha do PDF (definir antes de usar)
    with st.sidebar:
        st.header("🔐 Configurações PDF")
        pdf_password = st.text_input(
            "Senha do PDF (se protegido)",
            value=PDF_PASSWORD,
            type="password",
            help="Senha padrão para PDFs criptografados. Altere se seus PDFs usarem outra senha."
        )
        
        st.markdown("---")
        st.header("🤖 Configurações IA")
        gemini_model = st.selectbox(
            "Modelo Gemini",
            options=[
                "models/gemini-2.5-flash",
                "models/gemini-2.5-pro", 
                "models/gemini-2.0-flash",
                "models/gemini-flash-latest",
                "models/gemini-pro-latest"
            ],
            index=0,
            help="Escolha o modelo do Google Gemini. 'gemini-2.5-flash' é recomendado para melhor performance."
        )
    
    # Upload de arquivos
    uploaded_files = st.file_uploader(
        "Faça upload de um ou mais extratos bancários (PDF)",
        type=["pdf"],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        st.info(f"📄 {len(uploaded_files)} arquivo(s) selecionado(s)")
        
        if st.button("🚀 Processar Extratos", type="primary"):
            all_transactions = []
            processing_results = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, pdf_file in enumerate(uploaded_files):
                try:
                    status_text.text(f"Processando {pdf_file.name}... ({idx + 1}/{len(uploaded_files)})")
                    progress_bar.progress((idx) / len(uploaded_files))
                    
                    # Extrair texto (usar senha configurada na sidebar)
                    text = extract_text_from_pdf(pdf_file, password=pdf_password)
                    
                    if not text or len(text.strip()) == 0:
                        raise Exception("PDF não contém texto extraível")
                    
                    # Identificar banco
                    bank_name = identify_bank(text, pdf_file.name)
                    
                    # Chamar Gemini API (usar modelo selecionado na sidebar)
                    gemini_response = call_gemini_api(text, bank_name, model_name=gemini_model)
                    
                    # Parsear resposta
                    transactions = parse_gemini_response(gemini_response)
                    
                    if transactions:
                        # Adicionar banco a cada transação
                        for trans in transactions:
                            trans["banco"] = bank_name
                            all_transactions.append(trans)
                        
                        processing_results.append({
                            "arquivo": pdf_file.name,
                            "banco": bank_name,
                            "transacoes": len(transactions),
                            "status": "✅ Sucesso"
                        })
                    else:
                        processing_results.append({
                            "arquivo": pdf_file.name,
                            "banco": bank_name,
                            "transacoes": 0,
                            "status": "⚠️ Nenhuma transação encontrada"
                        })
                    
                except Exception as e:
                    error_msg = str(e)
                    save_error_log(error_msg, pdf_file.name, f"Erro durante processamento")
                    processing_results.append({
                        "arquivo": pdf_file.name,
                        "banco": "N/A",
                        "transacoes": 0,
                        "status": f"❌ Erro: {error_msg[:50]}..."
                    })
                    st.error(f"Erro ao processar {pdf_file.name}: {error_msg}")
            
            progress_bar.progress(1.0)
            status_text.text("Processamento concluído!")
            
            # Exibir resultados
            st.markdown("### 📊 Resultados do Processamento")
            results_df = st.dataframe(processing_results, use_container_width=True)
            
            # Enviar para n8n se houver transações
            if all_transactions:
                st.markdown(f"### 📤 Enviando {len(all_transactions)} transação(ões) para n8n...")
                
                try:
                    # Determinar banco principal (mais comum ou "Múltiplos" se houver vários)
                    banks_count = {}
                    for trans in all_transactions:
                        bank = trans.get("banco", "Desconhecido")
                        banks_count[bank] = banks_count.get(bank, 0) + 1
                    
                    if len(banks_count) == 1:
                        bank_name = list(banks_count.keys())[0]
                    else:
                        bank_name = "Múltiplos"
                    
                    # Preparar transações para envio (manter banco em cada transação para referência)
                    transactions_to_send = []
                    for trans in all_transactions:
                        # Criar cópia sem o campo banco no nível da transação (já está no payload principal)
                        trans_copy = {
                            "data": trans["data"],
                            "descricao": trans["descricao"],
                            "valor": trans["valor"],
                            "categoria": trans["categoria"]
                        }
                        transactions_to_send.append(trans_copy)
                    
                    result = send_to_n8n(transactions_to_send, bank_name)
                    st.success(f"✅ {len(transactions_to_send)} transação(ões) enviada(s) com sucesso para n8n!")
                    
                    # Exibir preview das transações
                    with st.expander("👁️ Visualizar Transações Enviadas"):
                        preview_data = []
                        for trans in all_transactions[:10]:
                            preview_data.append({
                                "data": trans["data"],
                                "descricao": trans["descricao"][:50] + "..." if len(trans["descricao"]) > 50 else trans["descricao"],
                                "valor": trans["valor"],
                                "categoria": trans["categoria"],
                                "banco": trans["banco"]
                            })
                        st.json(preview_data)
                        if len(all_transactions) > 10:
                            st.info(f"... e mais {len(all_transactions) - 10} transações")
                
                except Exception as e:
                    error_msg = str(e)
                    save_error_log(error_msg, "Múltiplos arquivos", "Erro ao enviar para n8n")
                    st.error(f"❌ Erro ao enviar para n8n: {error_msg}")
            else:
                st.warning("⚠️ Nenhuma transação foi extraída dos PDFs.")
    
    # Sidebar com instruções
    with st.sidebar:
        st.markdown("---")
        st.header("ℹ️ Instruções")
        st.markdown("""
        1. **Configure as variáveis de ambiente** no arquivo `.env`:
           - `GOOGLE_API_KEY`: Sua chave da API Google Gemini
           - `N8N_WEBHOOK_URL`: URL do webhook do n8n
        
        2. **Faça upload dos PDFs** dos extratos bancários
        
        3. **Clique em "Processar Extratos"** para iniciar
        
        4. As transações serão automaticamente:
           - Extraídas do PDF
           - Categorizadas pela IA
           - Enviadas para o n8n
        """)
        
        st.markdown("---")
        st.header("📋 Estrutura Google Sheets")
        st.markdown("""
        Configure as seguintes colunas no Google Sheets:
        
        1. **Data** (DD/MM/AAAA)
        2. **Descrição** (texto)
        3. **Valor** (número)
        4. **Categoria** (texto)
        5. **Banco** (texto)
        """)
        
        st.markdown("---")
        st.header("📁 Categorias")
        st.markdown(", ".join(CATEGORIAS_PERMITIDAS))


if __name__ == "__main__":
    main()

