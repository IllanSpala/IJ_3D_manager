# Guia de Instalação: IJ 3D Manager (Ambiente Linux)

Este documento detalha o processo passo a passo para instalar e executar o gerenciador de impressão 3D em sistemas Debian/Ubuntu. O projeto utiliza um ambiente virtual (`venv`) para isolar suas dependências, garantindo separação lógica das bibliotecas globais do sistema operacional.

---

## 1. Dependências de Sistema (A Infraestrutura)

Antes de isolar o ambiente, o sistema operacional precisa dos pacotes básicos para suportar ambientes virtuais e renderização de janelas gráficas.

Abra o terminal na pasta raiz do projeto e execute:
```bash
sudo apt update
sudo apt install python3-venv python3-tk
```

- `python3-venv`: Ferramenta nativa para criar diretórios de ambiente virtual isolados.
- `python3-tk`: A base gráfica. Conecta o código Python ao servidor de display do Linux (X11/Wayland) para renderizar a janela da aplicação na tela.

---

## 2. Criação do Ambiente Virtual (A Sala Limpa)

Com a permissão do sistema concedida, gere a estrutura de pastas do ambiente virtual:

```bash
python3 -m venv venv
```

Isso cria uma pasta `venv/` no diretório atual com um ecossistema Python limpo e isolado.

> ⚠️ **Importante:** A pasta `venv/` **não deve ser enviada ao repositório Git**. Ela já está listada no `.gitignore` e deve ser criada individualmente por cada usuário em sua própria máquina.

---

## 3. Ativação do Ambiente (Entrando no Workspace)

Para garantir que as instalações a seguir ocorram dentro do ambiente isolado:

```bash
source venv/bin/activate
```

> Você saberá que deu certo quando a tag `(venv)` aparecer no início da linha de comando do terminal.

---

## 4. Instalação das Dependências Python (As Ferramentas de Precisão)

Com o ambiente ativo, instale todas as bibliotecas listadas no manifesto do projeto:

```bash
pip install -r requirements.txt
```

O arquivo `requirements.txt` contém os pacotes necessários para o funcionamento da aplicação:

- `customtkinter`: Responsável pela interface moderna, escura e com cantos arredondados.
- `Pillow (PIL)`: Ferramenta de processamento de imagens, necessária para carregar e exibir fotos na interface.

---

## 5. Execução da Aplicação (Ligando o Motor)

Com as dependências instaladas, o ambiente está pronto. Certifique-se de que a tag `(venv)` está ativa e execute:

```bash
python3 app.py
```

> **Primeira execução:** O banco de dados SQLite (`print_manager_v2.db`) é criado **automaticamente** pelo próprio `app.py` caso não exista. Não é necessário nenhum passo manual de configuração do banco de dados.

> **Uso contínuo:** Sempre que fechar o terminal e quiser abrir o programa em outro dia, basta abrir o terminal na pasta do projeto e executar os **passos 3 e 5** em sequência.

---

## Estrutura do Repositório

```
IJ-3D-Manager/
├── app.py              # Código-fonte principal da aplicação
├── requirements.txt    # Manifesto de dependências Python
├── .gitignore          # Exclui venv/, *.db e outros arquivos gerados
├── app_icon.png        # Ícone da aplicação (opcional)
└── README.md           # Este guia
```

> Os arquivos `*.db` (banco de dados SQLite) são **gerados localmente** e **não fazem parte do repositório**. Cada instalação cria e mantém seu próprio banco de dados de operação.
