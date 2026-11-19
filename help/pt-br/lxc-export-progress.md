# Andamento da exportação de contêiner

Esta página mostra o andamento de uma exportação de contêiner em tempo real. Ela se atualiza sozinha — não precisa recarregar.

## Etapas

A exportação passa por várias etapas:
1. **Snapshot** — o Proxmox tira um snapshot do contêiner em execução usando o vzdump
2. **Pacote** — o backup e os metadados de configuração são juntados num arquivo `.px`
3. **Concluído** — o pacote está pronto para baixar

Cada etapa mostra o estado atual (pendente, em andamento ou concluída) conforme o job avança.

## Quando a exportação termina

Aparece uma mensagem de sucesso com as opções:
- **Baixar pacote .px** — salva o arquivo exportado no seu computador
- **Voltar ao contêiner** — volta para a página de detalhes do contêiner
- **Todas as exportações** — vai para a central de exportação/importação

Por padrão, o pacote fica no servidor por **24 horas** (`EXPORT_RETENTION_HOURS` no `.env`). Se *Remover o pacote deste servidor logo depois do download* estiver marcado, ele é apagado assim que um download termina por completo; um download interrompido não o remove.

## Se a exportação falhar

Aparece uma mensagem com o motivo da falha. Causas comuns:
- **Armazenamento insuficiente** — o armazenamento do dump não tem espaço livre suficiente para o backup
- **Contêiner bloqueado** — outra operação (backup, snapshot) já está rodando neste contêiner
- **Tempo esgotado na API** — a API do Proxmox não respondeu a tempo; o contêiner pode ser muito grande

Você pode voltar à página de detalhes do contêiner e tentar de novo.
