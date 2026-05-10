# Publicar no GitHub

Como o ambiente do Cowork não consegue executar `git` na pasta montada, você roda os comandos no seu Terminal local. São quatro passos.

## 1. Limpar qualquer git parcial e inicializar

Abre o Terminal e cola:

```bash
cd "/Users/llustosa/Library/Application Support/Claude/local-agent-mode-sessions/634bbf98-e940-4147-9a01-74d4eb46289b/633a48cd-c469-464b-807e-a7ad3259e72e/local_e4763f5a-4f70-4123-8d73-ea3399cd7906/outputs/aat-multiroom-ha"

rm -rf .git
git init -b main
git config user.email "lcaetano@gmail.com"
git config user.name "Leandro Lustosa"
git add .
git commit -m "Initial release: AAT Multiroom Digital integration for Home Assistant"
```

Confirme que rodou: `git log --oneline` deve mostrar um commit.

> Dica: se preferir manter o projeto numa pasta mais simples, copie a pasta inteira para `~/Documents/aat-multiroom-ha` antes do `git init` e use esse caminho daqui pra frente.

## 2. Criar o repositório vazio no GitHub

Vai em <https://github.com/new> e preenche:

- **Repository name**: `aat-multiroom-ha`
- **Description**: `Home Assistant integration for AAT Digital Multiroom amplifiers (PMR-4/5/6/7/8)`
- **Public** ou **Private** — sua escolha. Público se quiser que outros usem; privado se for só pra você.
- **Importante**: NÃO marque "Add a README", "Add .gitignore" ou "Choose a license" — você já tem esses arquivos localmente, o GitHub criar de novo gera conflito.

Clica em **Create repository**.

A próxima tela mostra um bloco "...or push an existing repository from the command line" com os comandos prontos. Use os comandos abaixo (são iguais, mas com seu user já preenchido).

## 3. Conectar e enviar

No mesmo Terminal:

```bash
git remote add origin https://github.com/lcaetano/aat-multiroom-ha.git
git push -u origin main
```

Na primeira vez o GitHub vai pedir autenticação:

- Se aparecer pop-up do macOS Keychain perguntando senha → entra com sua senha do GitHub.
- Se for via terminal e pedir Username/Password → usa seu username (`lcaetano`) e um **Personal Access Token** como senha (não a senha da conta).

Se você nunca criou um token: <https://github.com/settings/tokens?type=beta> → "Generate new token" → marca acesso ao repositório `aat-multiroom-ha` com permissão **Contents: Read and write**. Copia o token que aparece e usa como senha.

> Alternativa mais cômoda: instala o [GitHub CLI](https://cli.github.com/) (`brew install gh` no macOS), faz `gh auth login` uma vez e nunca mais precisa lidar com token — o `git push` passa a funcionar direto.

## 4. Confirma que foi

Abre `https://github.com/lcaetano/aat-multiroom-ha` no navegador. Deve estar lá com README, código, exemplos, tudo.

---

## Próximos commits

Daqui pra frente, conforme você for ajustando coisas, é só:

```bash
git add .
git commit -m "uma descrição curta da mudança"
git push
```

E o repositório no GitHub atualiza.

## Se algo der errado

**`fatal: remote origin already exists`**
: Você já adicionou um remote antes. Remove com `git remote remove origin` e adiciona de novo.

**`error: failed to push some refs ... rejected`**
: Quase sempre acontece quando o repo no GitHub foi criado com README e o seu local não tem ele. Resolve com `git pull origin main --allow-unrelated-histories` e depois `git push`. Em último caso, refaz o repo no GitHub do zero (sem nenhum arquivo inicial).

**Push pede senha mesmo eu já tendo logado**
: Macs guardam credenciais no Keychain mas às vezes resetam. Roda `git config --global credential.helper osxkeychain` uma vez.
