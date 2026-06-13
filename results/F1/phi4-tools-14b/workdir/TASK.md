# TASK — Site Imobiliário Casa Certa Imóveis

## Objetivo
Criar e publicar um site imobiliário completo com dados em arquivo separado, filtro interativo e design profissional.

## Arquivos a criar

### 1. `imoveis.json`
JSON com exatamente **6 imóveis**. Cada imóvel deve ter os campos:
```
id, tipo, titulo, endereco, preco, area_m2, quartos, foto
```

- `tipo` deve ser um de: `Apartamento`, `Casa`, `Terreno`
- Distribuição mínima: 2 Apartamentos, 2 Casas, 2 Terrenos
- `foto`: use `https://placehold.co/400x300`

### 2. `index.html`
Site completo da agência **Casa Certa Imóveis**.

#### Design
- Paleta obrigatória:
  - Primária: `#1B4332`
  - Secundária: `#40916C`
  - Fundo claro: `#D8F3DC`
  - Texto escuro: `#081C15`
- Fonte: Google Fonts (qualquer sans-serif moderna)
- Layout responsivo com breakpoint em `768px`
- Mobile: hamburger menu que abre/fecha a navegação

#### Seções obrigatórias (com IDs)
| ID | Conteúdo |
|----|----------|
| `#hero` | Headline forte + CTA |
| `#imoveis` | Grade de imóveis carregados via fetch |
| `#sobre` | Sobre Nós da agência |
| `#contato` | Formulário de contato |

#### JavaScript obrigatório
1. `fetch('./imoveis.json')` para carregar os imóveis — **não hardcode o array no HTML**
2. Botões de filtro por tipo: `[Todos]` `[Apartamento]` `[Casa]` `[Terreno]`
3. Validação do formulário:
   - Nome: obrigatório
   - E-mail: formato válido (`input.validity.typeMismatch`)
   - Mensagem: obrigatória
   - Erros exibidos inline abaixo de cada campo

#### CSS obrigatório
- `@media (max-width: 768px)` para grid de imóveis (1 coluna) e menu mobile

## Servidor
Após criar os dois arquivos, inicie o servidor HTTP:
```bash
nohup python3 -m http.server 8500 --directory . > /dev/null 2>&1 &
```
Aguarde 2 segundos e verifique:
```bash
curl -s -o /dev/null -w '%{http_code}' http://localhost:8500/
```

## Conclusão
Quando o servidor estiver respondendo `200`, responda com:
```
PÁGINA PUBLICADA: http://localhost:8500/
```
