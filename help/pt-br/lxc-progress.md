# Criando contêiner — andamento

Esta página mostra o andamento da criação de um contêiner em tempo real. Ela se atualiza sozinha — não precisa recarregar.

## Etapas

A criação passa por várias etapas. Cada uma mostra o estado atual (pendente, em andamento ou concluída) conforme o job avança.

## Quando a criação termina

Aparece uma mensagem de sucesso com o nome e o CTID do contêiner, e as opções:
- **Ver contêineres** — vai para o inventário de contêineres
- **Criar outro** — começa outro contêiner a partir de um template

## Se a criação falhar

Aparece uma mensagem com o motivo da falha. Causas comuns:
- **CTID em conflito** — outro contêiner com o CTID escolhido foi criado entre a configuração e a implantação. Tente de novo com outro CTID ou deixe em branco para atribuir automaticamente.
- **Armazenamento insuficiente** — o pool de armazenamento não tem espaço livre suficiente para o rootfs do contêiner.
- **Template não encontrado** — o template escolhido pode ter sido excluído do armazenamento.
- **Nome do host inválido** — o nome tem caracteres que o Proxmox não aceita.

Clique em **Tentar de novo** para voltar à configuração com os valores anteriores, ou em **Começar de novo** para escolher outro template.
