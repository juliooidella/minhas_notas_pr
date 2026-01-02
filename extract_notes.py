import asyncio
import pandas as pd
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
import os
import getpass
import os
from dotenv import load_dotenv

load_dotenv()

# Configuração
MAX_MONTHS = 3  # Quantos meses recentes processar

# Helper function for user input in async context
async def get_input(text):
    return await asyncio.get_event_loop().run_in_executor(None, input, text)

async def get_pass(text):
    return await asyncio.get_event_loop().run_in_executor(None, getpass.getpass, text)

def parse_nfce(soup, data):
    """
    Parses NFC-e (Consumer Electronic Invoice) HTML content.
    """
    try:
        # Data de Emissão
        emissao_match = soup.find("strong", string=re.compile("Emissão"))
        if emissao_match:
            raw_date = emissao_match.next_sibling.strip()
            # Clean date: extrai apenas dd/mm/yyyy [hh:mm:ss], removendo "- Via Consumidor", offsets de fuso horário, etc.
            match = re.search(r'(\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}:\d{2})?)', raw_date)
            data["data_emissao"] = match.group(1) if match else raw_date.split(" -")[0].strip()

        # Número da Nota
        numero_match = soup.find("strong", string=re.compile("Número:"))
        if numero_match:
            data["numero"] = numero_match.next_sibling.strip()

        # Estabelecimento
        # NFC-e: <div class="txtCenter"> <div id="u20" class="txtTopo">NAME</div> ...
        header_div = soup.select_one("div.txtCenter div#u20.txtTopo")
        if header_div:
            data["estabelecimento"] = header_div.get_text(strip=True)
        else:
            # Fallback
            top_header = soup.select_one(".ui-content div.txtCenter .txtTit")
            if top_header:
                data["estabelecimento"] = top_header.get_text(strip=True)

        # Itens
        items_table = soup.select_one("table#tabResult")
        if items_table:
            rows = items_table.find_all("tr", id=re.compile(r"^Item"))
            for row in rows:
                item_data = {}
                name_el = row.select_one(".txtTit2")
                item_data["produto"] = name_el.get_text(strip=True) if name_el else "N/A"
                
                qtd_el = row.select_one(".Rqtd")
                if qtd_el:
                    txt = qtd_el.get_text(strip=True)
                    item_data["quantidade"] = txt.replace("Qtde.:", "").strip()
                else:
                    item_data["quantidade"] = "1"
                
                val_el = row.select_one(".valor")
                item_data["valor_item"] = val_el.get_text(strip=True) if val_el else "0,00"

                data["itens"].append(item_data)
                
    except Exception as e:
        print(f"Erro ao fazer parse de NFC-e: {e}")

def parse_nfe(soup, data):
    """
    Parses NF-e (Electronic Invoice) HTML content.
    """
    try:
        labels = soup.find_all("label")
        for lb in labels:
            lb_text = lb.get_text()
            # Use a more flexible match for "Data de Emissão" to avoid encoding issues
            if "Data" in lb_text and "Emiss" in lb_text:
                val_span = lb.find_next_sibling("span")
                if val_span:
                    raw_date = val_span.get_text(strip=True)
                    # Clean date: extrai apenas dd/mm/yyyy [hh:mm:ss], removendo offsets como -03:00
                    match = re.search(r'(\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}:\d{2})?)', raw_date)
                    data["data_emissao"] = match.group(1) if match else raw_date.split(" -")[0].strip()
                    break

        # Número da Nota NF-e
        for lb in labels:
            if "Número" in lb.get_text():
                val_span = lb.find_next_sibling("span")
                if val_span:
                    data["numero"] = val_span.get_text(strip=True)
                    break
        
        # Estabelecimento NF-e
        # User tip: //*[@id="NFe"]/fieldset[2]/table/tbody/tr/td[2]
        # Trying to locate via ID #NFe and structure
        nfe_div = soup.select_one("#NFe")
        if nfe_div:
            # Fieldsets
            fieldsets = nfe_div.find_all("fieldset")
            if len(fieldsets) >= 2:
                sec_fieldset = fieldsets[1] # 2nd fieldset
                # First table in this fieldset
                tbl = sec_fieldset.find("table")
                if tbl:
                    # first row, second cell
                    row = tbl.find("tr")
                    if row:
                        cols = row.find_all("td")
                        if len(cols) >= 2:
                             # Limpa o rótulo que às vezes vem junto no get_text()
                             est_text = cols[1].get_text(strip=True)
                             est_text = est_text.replace("Nome / Razão Social", "").strip()
                             data["estabelecimento"] = est_text

        tables = soup.select("table.box")
        current_item = {}
        
        for tbl in tables:
            text_content = tbl.get_text()
            if "Código do Produto" in text_content:
                q_lbl = tbl.find("label", string=re.compile("Quantidade Comercial"))
                if q_lbl:
                    span = q_lbl.find_next_sibling("span")
                    if span:
                        current_item["quantidade"] = span.get_text(strip=True)
                
                v_lbl = tbl.find("label", string=re.compile("Valor unitário de comercialização"))
                if v_lbl:
                    span = v_lbl.find_next_sibling("span")
                    if span:
                        current_item["valor_item"] = span.get_text(strip=True)
                
                current_item["produto"] = "Produto NF-e"
                
                if current_item:
                     data["itens"].append(current_item)
                     current_item = {}

    except Exception as e:
        print(f"Erro ao fazer parse de NF-e: {e}")

async def scrape_invoice(context, url):
    page = await context.new_page()
    result_data = {
        "url": url,
        "tipo": "Desconhecido",
        "numero": "",
        "estabelecimento": "",
        "data_emissao": "",
        "itens": []
    }
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(1000)
        
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        if soup.select_one("#tabResult"):
            result_data["tipo"] = "NFC-e"
            parse_nfce(soup, result_data)
        elif "Consulta Completa NF-e" in soup.get_text() or soup.select_one("fieldset legend"):
             result_data["tipo"] = "NF-e"
             parse_nfe(soup, result_data)
        
        return result_data

    except Exception as e:
        print(f"Erro ao processar {url}: {e}")
        return None
    finally:
        await page.close()

async def perform_login(page):
    print("\n--- Login Automático ---")
    
    # Using provided credentials. 
    # Use environment variables or prompt in production!
    cpf = os.getenv("CPF")
    password = os.getenv("PASSWORD")
    
    try:
        print("Preenchendo credenciais...")
        # Wait for the login form to be visible
        await page.wait_for_selector("#attribute", state="visible", timeout=10000)
        
        # Fill credentials
        await page.fill("#attribute", cpf)
        await page.fill("#password", password)
        
        print("Enviando formulário...")
        await page.click("input[type='submit']", timeout=5000)
        
        # Wait for navigation or error
        await page.wait_for_load_state("networkidle")
        
        # Check for error message
        error_msg = await page.locator("#error\\.message").is_visible()
        if error_msg:
            text = await page.locator("#error\\.message").inner_text()
            print(f"ALERTA: Mensagem de erro detectada no login: {text}")
            return False
            
        return True
    
    except Exception as e:
        print(f"Erro durante tentativa de login: {e}")
        return False

async def extract_month_links(page):
    """
    Extracts invoice links from the current view.
    """
    # Wait for potential ajax load
    await page.wait_for_timeout(2000)
    
    hrefs = await page.evaluate(r"""
        () => {
            const links = Array.from(document.querySelectorAll('a'));
            return links
                .map(a => a.href)
                .filter(href => href.includes('NotaFiscalHtml') || href.includes('idDocFiscal'));
        }
    """)
    return list(set(hrefs))

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("--- Automação Nota Paraná ---")
        
        try:
            print("Acessando página inicial...")
            await page.goto("https://notaparana.pr.gov.br/", wait_until="networkidle")
            
            # Check if we are on login page
            if await page.locator("#authForm").count() > 0 or await page.locator("#attribute").count() > 0:
                success = await perform_login(page)
                if not success:
                    print("Login falhou. Tente novamente ou verifique as credenciais.")
                    # Allow manual intervention just in case
                    await asyncio.sleep(5)
            else:
                print("Parece que já estamos logados ou página desconhecida.")

            # Verificação de Múltiplas Sessões (Tela de Erro)
            # Ex: "O usuário autenticado possui mais de uma sessão ativa."
            # Botão: Encerrar todas as sessões ativas!
            # Texto no botão/pag: Encerrar todas as sessões ativas!
            try:
                # Check for the specific button or message
                multiple_sessions_btn = page.locator("button", has_text="Encerrar todas as sessões ativas!")
                if await multiple_sessions_btn.count() > 0 and await multiple_sessions_btn.is_visible():
                    print("ALERTA: Múltiplas sessões ativas detectadas.")
                    print("Tentando encerrar sessões anteriores...")
                    await multiple_sessions_btn.click()
                    await page.wait_for_timeout(3000) # Wait for redirect
                    
                    # After clicking, it might redirect to login again.
                    # Let's check if we are back at login
                    if await page.locator("#authForm").count() > 0:
                        print("Redirecionado para login após encerrar sessões. Tentando logar novamente...")
                        success = await perform_login(page)
                        if not success:
                            print("Falha no re-login.")
                            await browser.close()
                            return
            except Exception as e:
                print(f"Erro ao verificar sessões ativas: {e}")

            print("Aguardando carregamento pós-login...")
            await page.wait_for_timeout(3000)

            # Navigate specifically to 'Extrato' as requested
            target_url = "https://notaparana.pr.gov.br/nfprweb/Extrato"
            print(f"Navegando para: {target_url}")
            await page.goto(target_url, wait_until="networkidle")
            
            print("Aguardando carregamento da tabela de notas...")
            try:
                # Wait for the table to be visible
                await page.wait_for_selector("#minhasnotas", state="visible", timeout=15000)
            except:
                print("Tabela #minhasnotas não encontrada automaticamente.")
                print("Por favor, verifique se você está na tela correta.")
                await get_input("Pressione ENTER se a lista estiver visível...")

            # Locate month rows
            print("Identificando meses disponíveis...")
            
            # Get all rows in the 'minhasnotas' table body
            rows = page.locator("#minhasnotas tbody tr")
            count = await rows.count()
            print(f"Encontradas {count} linhas de meses.")
            
            all_invoice_links = set()
            
            # Iterate through rows
            months_processed = 0
            for i in range(count):
                if months_processed >= MAX_MONTHS:
                    print(f"Limite de {MAX_MONTHS} meses atingido.")
                    break

                row = rows.nth(i)
                id_val = await row.get_attribute("id")
                txt = await row.inner_text()
                
                # Check if it looks like a month row
                if id_val and len(id_val) == 8: # e.g. 12012025
                    month_label = txt.split("\n")[0] if txt else "Mês desconhecido"
                    print(f"Processando: {month_label}")
                    
                    try:
                        # Click the row to load notes for that month using JS to ensure it triggers
                        await row.evaluate("el => el.click()")
                        
                        # Wait for notes to load.
                        await page.wait_for_timeout(3000) 
                        
                        # Extract links
                        links = await extract_month_links(page)
                        new_links = 0
                        for l in links:
                            if l not in all_invoice_links:
                                all_invoice_links.add(l)
                                new_links += 1
                        
                        print(f"  > Encontrados {len(links)} links ({new_links} novos)")
                        
                        months_processed += 1
                        
                    except Exception as e:
                        print(f"  > Erro ao processar mês {id_val}: {e}")

            print(f"\nTotal de links únicos coletados: {len(all_invoice_links)}")
            
            if len(all_invoice_links) == 0:
                print("Nenhum link. Encerrando.")
                await browser.close()
                return

            print("\nIniciando download das notas (Processamento Paralelo)...")
            
            sem = asyncio.Semaphore(5)
            
            async def bounded_scrape(url):
                async with sem:
                    await asyncio.sleep(0.1)
                    print(f"Baixando: {url}")
                    return await scrape_invoice(context, url)

            tasks = [bounded_scrape(url) for url in all_invoice_links]
            results = await asyncio.gather(*tasks)
            
            # Process results
            flat_rows = []
            for res in results:
                if not res: continue
                
                base = {
                    "URL": res["url"],
                    "Tipo": res["tipo"],
                    "Número": res["numero"],
                    "Estabelecimento": res["estabelecimento"],
                    "Data Emissão": res["data_emissao"]
                }
                
                if res["itens"]:
                    for item in res["itens"]:
                        row = base.copy()
                        row["Produto"] = item.get("produto", "")
                        row["Quantidade"] = item.get("quantidade", "")
                        row["Valor Item"] = item.get("valor_item", "")
                        flat_rows.append(row)
                else:
                    row = base.copy()
                    row["Produto"] = "N/A"
                    row["Quantidade"] = ""
                    row["Valor Item"] = ""
                    flat_rows.append(row)

            if flat_rows:
                df = pd.DataFrame(flat_rows)
                
                # Add Ano-Mes column
                # Expected format: "dd/mm/yyyy HH:MM:SS" or similar
                try:
                    # Convert to datetime objects first
                    # dayfirst=True is important for dd/mm/yyyy
                    df['dt_obj'] = pd.to_datetime(df['Data Emissão'], dayfirst=True, errors='coerce')
                    df['Ano-Mes'] = df['dt_obj'].dt.strftime('%Y-%m')
                    df.drop(columns=['dt_obj'], inplace=True)
                except Exception as e:
                    print(f"Erro ao processar coluna de data: {e}")
                    df['Ano-Mes'] = ""

                csv_path = "notas_parana_completo.csv"
                df.to_csv(csv_path, index=False)
                print(f"\nSucesso! {len(flat_rows)} itens extraídos e salvos em '{csv_path}'.")
            else:
                print("Nenhum dado válido extraído.")
            
            print("\nRealizando logout...")
            try:
                await page.goto("https://notaparana.pr.gov.br/nfprweb/publico/sair")
                await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"Erro ao fazer logout: {e}")

        except Exception as e:
            print(f"Erro fatal: {e}")
        finally:
            print("Fechando navegador...")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
