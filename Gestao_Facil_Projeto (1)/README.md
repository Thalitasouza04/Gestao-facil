# Gestão Fácil

Aplicação web acadêmica para apoiar pequenos empreendedores no cadastro de produtos e clientes, registro de vendas e acompanhamento de estoque.

## Funcionalidades incluídas
- Criação de conta e login com senha armazenada em hash.
- Painel com resumo de produtos, clientes, vendas e receita.
- Cadastro e exclusão de produtos e clientes.
- Registro de venda com validação de estoque e atualização do estoque.
- Cancelamento de venda com devolução de estoque.
- Separação de dados por conta de usuário.
- Banco SQLite criado automaticamente.

## Requisitos
Python 3.10 ou superior.

## Executar no Windows
1. Instale o Python pelo site oficial e marque a opção para adicionar Python ao PATH.
2. Extraia a pasta do projeto.
3. Abra o Prompt de Comando dentro da pasta `gestao_facil`.
4. Execute:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

5. Abra no navegador: http://127.0.0.1:5000
6. Clique em “Criar conta” para registrar seu usuário.

## Executar no macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Depois abra http://127.0.0.1:5000.

## Antes de publicar
- Configure uma `SECRET_KEY` longa e aleatória em variável de ambiente.
- Use um serviço de hospedagem que suporte Flask e configure o armazenamento persistente do banco.
- Para uso real/comercial, implemente proteção CSRF, limitação de tentativas de login, logs, backups e testes automatizados. Esta versão é um protótipo acadêmico e precisa de revisão de segurança antes de uso real.
- O modo `debug=True` é somente para execução local. Desative-o na publicação.
- SQLite pode não ser adequado a todos os ambientes de hospedagem; confirme a persistência do disco ou migre para PostgreSQL.

## Testes manuais iniciais
1. Criar conta e entrar.
2. Tentar entrar com senha errada.
3. Cadastrar produto com preço válido e estoque 10.
4. Tentar cadastrar produto com preço inválido ou estoque negativo.
5. Cadastrar cliente.
6. Registrar venda com quantidade menor ou igual ao estoque.
7. Tentar vender quantidade maior que o estoque.
8. Cancelar venda e confirmar que o estoque voltou.
9. Criar segunda conta e verificar que não vê os dados da primeira.

## Estrutura
- `app.py`: rotas, regras de negócio e banco de dados.
- `templates/`: telas HTML.
- `static/style.css`: estilos.
- `instance/`: banco SQLite criado ao executar (não enviar credenciais/dados pessoais ao GitHub).
