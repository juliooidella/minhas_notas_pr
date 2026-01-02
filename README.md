# 📊 Minhas Notas PR

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Automated-green.svg)](https://playwright.dev/)
[![License](https://img.shields.io/badge/Privacidade-100%25_Local-brightgreen.svg)](#-segurança-e-privacidade)

O **Minhas Notas PR** é o seu assistente pessoal para o portal Nota Paraná. Ele automatiza aquela tarefa chata de baixar nota por nota, transformando tudo em uma planilha organizada e em relatórios de gastos inteligentes.

---

## ✨ Por que usar?

Se você coloca o CPF na nota, sabe que o portal do Nota Paraná é ótimo, mas extrair os detalhes do que você comprou pode demorar horas. 
Este projeto faz o trabalho pesado por você em minutos:
- **Automatiza o login** e a navegação entre meses.
- **Lê os detalhes** de cada produto (nome, quantidade, valor).
- **Consolida tudo** em um único lugar para você usar no Excel ou Google Sheets.
- **Te diz onde você está gastando**, separando automaticamente compras de mercado, farmácia e mais.

---

## 🔒 Segurança e Privacidade (Seus dados são SEUS)

A segurança é o pilar principal deste projeto. 
- **100% Local**: O código roda inteiramente no seu computador.
- **Sem Nuvem**: Nenhuma informação (CPF, senha, histórico de compras) é enviada para servidores externos.
- **Acesso Direto**: O script interage diretamente com o site oficial do Governo (`notaparana.pr.gov.br`).
- **Navegação Transparente**: Você pode acompanhar o navegador trabalhando em tempo real.

---

## 🛠️ Como Instalar (Para todos os níveis)

Não se preocupe se você não for desenvolvedor. Siga estes passos simples:

### 1. Preparar o terreno
Você precisará do **Python** e do **uv** (que gerencia tudo para você). Com eles instalados, abra seu terminal e digite:

```bash
# Sincroniza o projeto e baixa as ferramentas necessárias
uv sync

# Instala o navegador que o script vai usar
uv run playwright install chromium
```

### 2. Configurar seu acesso
Renomeie o arquivo `.env-example` para apenas `.env` e preencha com seu CPF e Senha do portal:
```ini
CPF=00011122233
PASSWORD=sua_senha_secreta
```
*Não se preocupe, este arquivo está configurado para ser ignorado pelo Git e nunca ser compartilhado.*

---

## 🚀 Como Usar

### Passo 1: Extrair os dados
Execute o motor de busca. Ele vai abrir o navegador, logar e coletar as notas dos meses que você desejar.
```bash
uv run extract_notes.py
```

### Passo 2: Analisar seus gastos
Após terminar a extração, você terá um arquivo chamado `notas_parana_completo.csv`. Agora, gere o relatório visual:
```bash
uv run analyze_data.py
```
Isso criará o arquivo **`analise_compras.md`**, que você pode abrir para ver seus produtos mais comprados e o total por categoria.

---

## ⚙️ Customização Fácil

Quer baixar mais ou menos meses? No topo do arquivo `extract_notes.py`, basta alterar este número:
```python
MAX_MONTHS = 3  # Mude para 12 se quiser o ano todo, por exemplo.
```

---

## � O que você recebe ao final
- **Planilha Completa (`.csv`)**: Ideal para quem ama filtros e tabelas dinâmicas no Excel.
- **Relatório de Insights (`.md`)**: Um resumo legível de "onde meu dinheiro está indo?".

---
*Este projeto foi criado para dar poder ao cidadão paranaense sobre seus próprios dados fiscais.*
