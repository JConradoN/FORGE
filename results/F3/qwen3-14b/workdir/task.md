# Tarefa

1. Busque as cotações atuais de:
   - Dólar (USD/BRL): use https://economia.awesomeapi.com.br/json/last/USD-BRL
   - Euro (EUR/BRL): use https://economia.awesomeapi.com.br/json/last/EUR-BRL
   - Bitcoin (BTC/BRL): use https://economia.awesomeapi.com.br/json/last/BTC-BRL
   - Ethereum (ETH/BRL): use https://economia.awesomeapi.com.br/json/last/ETH-BRL
   Use http_get para cada URL. Extraia os campos: bid (compra), ask (venda), pctChange (variação %), timestamp.

2. Busque o histórico recente de 7 dias para o Dólar:
   https://economia.awesomeapi.com.br/json/daily/USD-BRL/7
   Use para identificar a tendência (alta/queda/estável).

3. Gere um relatório de análise com as seções:
   - COTAÇÕES ATUAIS (tabela com todas as 4 moedas)
   - TENDÊNCIA DO DÓLAR (baseada no histórico de 7 dias)
   - ANÁLISE DE VOLATILIDADE (comparar variação % entre os 4 ativos)
   - RECOMENDAÇÃO (uma frase objetiva por ativo: momento de compra/venda/aguardar)
   - DATA/HORA DA ANÁLISE

4. Salve em './analise-mercado-qwen3-14b.md' usando write_file.

5. Envie um resumo via send_claudio com: as cotações principais e a tendência do dólar.

6. Responda com: 'ANÁLISE CONCLUÍDA: USD=[valor], BTC=[valor], tendência dólar=[alta/queda/estável]'