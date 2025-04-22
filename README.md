# dnsfw
Scripts construídos para realizar os experimentos de análise de performance da solução de DNS FW baseada em eBPF/XDP.<br>


## **dns_test.py**
Para realizar o teste de todos os percentuais de forma sequencial.<br>
```markdown
Uso: dns_test.py [-h] --all-percents {dnsfw_no,dnsfw_rpz,dnsfw_xdp}
```
Exemplo:
```console
python3 dns_test.py --all-percents dnsfw_xdp
```
## **teste_cpu.py**
Para realizar teste de um percentual especifico.<br>
```markdown
Uso: teste_cpu.py [-h] {dnsfw_no,dnsfw_rpz,dnsfw_xdp} {10,20,30,40,50,60,70,80,90}
```
Exemplo:
```console
python3 teste_cpu.py dnsfw_rpz 10
```
## **teste_vazao.py**
Realiza o teste de vazão total do servidor DNS usando o resperf.<br>
Utiliza um arquivo de entrada **query_file.txt**<br>
```markdown
Uso: teste_vazao.py [-h] {dnsfw_no,dnsfw_rpz,dnsfw_xdp}
```
Exemplo:
```console
python3 teste_vazao.py dnsfw_xdp
```
## **teste_latencia.py**
Realiza o teste da variação do tempo de resposta do servidor DNS para consultas de um domínio.<br>
Utiliza um arquivo de entrada **domains.txt**<br>
```markdown
Uso: teste_latencia.py [-h] {dnsfw_no,dnsfw_rpz,dnsfw_xdp}
```
Exemplo:
```console
python3 teste_latencia.py dnsfw_xdp
```

## Tools

**sar_parse.py**<p>
Realiza o parse do arquivo de log do SAR e converte em CSV<br>
Args:<br>
    input_file (str): Caminho do arquivo de log do SAR de entrada<br>

**make_domainfile.py**<p>
Lê os dois arquivos de entrada: blackbook.txt.2 e benign_domains.txt.<br>
Para cada percentual (10%, 20%, ..., 90%), cria um arquivo com 1.000 linhas.<br>
O script embaralha cada grupo de 10 linhas para que a distribuição não seja previsível dentro do grupo.

**convert_rpz.py**<p>
Converte uma lista de domínios para o formato RPZ.<br>
Args:<br>
        input_file (str): Caminho do arquivo de entrada com um domínio por linha.<br>
        output_file (str): Caminho do arquivo de saída no formato RPZ.<br>





