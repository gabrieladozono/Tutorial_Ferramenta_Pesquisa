#  Tutorial: Como Rodar uma ferramente de pesquisa no VSCode

Este tutorial explica **passo a passo** como rodar um **ferramenta de pesquisa** dentro do **VSCode**, desde a instalação até a execução completa.  
O objetivo é ajudar usuários a entenderem como **abrir e testar fluxos** no ambiente Langflow de forma prática.

---

## 1. Baixando o VSCode

Antes de começar, é necessário ter o **VSCode** instalado no seu computador. É possível baixar por lojas de aplicativos, site do VSCode.

## 2. Baixando o Python
Depois de instalado é necessário baixar o Python. Ele pode ser baixado nas extensões dentro do VSCode, ou pelo terminal.

### 2.1 Pelas extensões do VSCode

- Abra a aba de extensões e procure "python" e clique instalar.

<p align="center">
  <img src="imagens/python.png" alt="Extensão python" width="400">
</p>

> Agora o Python está instalado.

### 2.2 Pelo terminal

- No terminal rode

```bash
pip install python
```
> Agora o Python está instalado.

## 3. Abrindo uma pasta e arquivo
Para rodar a ferramenta é necessário que o arquivo esteja dentro de uma pasta local.
- Crie uma pasta com o nome desejado.
- No VSCode, clique em abrir pasta

<p align="center">
  <img src="imagens/abrirpasta.png" alt="Extensão python" width="400">
</p>

- Adicione um arquivo e de um nome que acabe com .py

Por exemplo: pesquisa.py

- Copie o conteúdo do arquivo abaixo e cole dentro do arquivo.

👉🏼 [Clique aqui para visualizar e copiar o arquivo `pesquisa.py`](codigo/pesquisa.py)

## 4. Recursos necessários
Para o código funcionar é necessário instalar dois recursos, o pandas e o openpyxl

Para isso digite no terminal:

```bash
pip install pandas openpyxl
```

## 5. Modificações necessárias
Esse código está genérico no momento, então é necessário alterar algumas informações de acordo com a planilha desejada.

### 5.1 Caminho da Planilha
Para adicionar a planilha no código:
- Adicione a planilha dentro da pasta do projeto.
- Troque o nome da planilha dentro do código. É necessário trocar na linha 96 e na linha 387.

<p align="center">
  <img src="imagens/planilha1.png" alt="Planilha 1" width="400">
</p>

<p align="center">
  <img src="imagens/planilha2.png" alt="Planilha 2" width="400">
</p>

## 5.2 Adicionar termos substitutos 
Para facilitar na hora de realizar a pesquisa, é necessário definir termos que indiquem em qual coluna a ferramenta deve olhar de acordo com a pesquisa desejada.

- A partir da linha 9, você pode adicionar diversos termos para as colunas da sua planilha. Apenas siga o formato disponibilizado no código.

<p align="center">
  <img src="imagens/termos.png" alt="Mapeamento de termos" width="400">
</p>

## 5.2 Modificando a entrada
No final de código a o formato da entrada que vai rodar o código. É necessário alterar essa entrada de acordo com a pesquisa desejada.

Supondo que minha planilha tenha dados de passageiros do Titanic, e eu queira saber a média de idade dos passegeiros que sobreviveram, substituirei entrada por:

```bash
entrada = {
  "column_operation": ["idade"],
  "operation": ["media"],
  "comparisons": [], 
  "ranking": [],
  "group_by": [],
  "correlation": [],
  "percentage": [],
  "special_conditions": [],
  "data": [
      {"column_name": "sobreviveram", "value": "1"}
      ]
}
```

## 6. Explicação de cada variável da entrada
- Column_operation : Aqui você define qual coluna será realizada a operação.
- Operation: Aqui você define qual operação será realizada. Há uma grande variedade de operações possíveis, como listar, média, diferença, soma, etc. Todas as operações podem ser encontradas no código a partir da linha 247.

<p align="center">
  <img src="imagens/operacoes.png" alt="Operações possíveis" width="400">
</p>

- Comparisons: Calcula a correlação estatística entre as colunas. Exemplo:

