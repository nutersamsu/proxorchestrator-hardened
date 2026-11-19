# Tarefas

Esta página é o **histórico de tarefas** do nó no Proxmox, a mesma lista que
aparece em *Node → Task History* na interface web do Proxmox. Toda operação
demorada (iniciar, parar, backup, clonar, sessão de console, atualização de
pacotes…) cria uma tarefa, não importa quem começou: este app, a interface do
Proxmox, o `qm`/`pct` no shell ou um job agendado.

## Filtros

- **VMID**: só as tarefas de uma VM ou contêiner.
- **Tipo**: o tipo da tarefa (por exemplo *Backup* = `vzdump`, *VM start* = `qmstart`).
- **Usuário**: quem começou, ex.: `root@pam` ou `proxorchestrator@pve`.
- **Só erros** / **Só em execução**.

## Log da tarefa

Clique numa tarefa para ver a saída completa. Enquanto a tarefa roda, o log
se atualiza a cada 2 segundos e aparece um botão **Parar**.

O token da API só pode parar as tarefas que ele mesmo começou. Parar tarefas
de outros usuários exige o privilégio `Sys.Modify`, que o token recomendado
não tem.

## Barra de tarefas recentes

A barra no rodapé de todas as páginas mostra as seis últimas tarefas e se
atualiza a cada 10 segundos. Clique no título para recolhê-la; a escolha fica
guardada neste navegador.

## Horários

Os horários aparecem no fuso horário do servidor. Para mudar, defina
`TIME_ZONE` no `.env` do app (por exemplo `TIME_ZONE=Europe/Rome`) e rode o
`update.sh`.
