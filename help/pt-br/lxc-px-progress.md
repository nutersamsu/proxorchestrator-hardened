# Importar contêiner — andamento

Esta página mostra em tempo real o andamento da importação de um contêiner (implantação a partir de um pacote `.px`). Ela se atualiza sozinha — não precisa recarregar.

## Etapas

A importação passa por várias etapas:
1. **Transferência** — o arquivo de backup é transferido para o armazenamento do nó Proxmox
2. **Restauração** — o Proxmox restaura o contêiner a partir do backup com `pct restore`
3. **Configuração** — rede, recursos e opções são aplicados ao contêiner restaurado
4. **Início** (se marcado) — o contêiner é ligado depois da restauração
5. **Concluído** — o contêiner está pronto

Cada etapa mostra o estado atual (pendente, em andamento ou concluída) conforme o job avança.

## Quando a importação termina

Aparece uma mensagem de sucesso com o nome e o CTID do contêiner, e as opções:
- **Ver contêiner** — vai para a página de detalhes do novo contêiner
- **Importar outro** — envia outro pacote `.px`
- **Exportações e importações** — volta para a central de exportação/importação

## Se a importação falhar

Aparece uma mensagem com o motivo da falha. Causas comuns:
- **CTID em conflito** — outro contêiner com o CTID escolhido foi criado entre a configuração e a implantação. Tente de novo com outro CTID.
- **Armazenamento insuficiente** — o pool não tem espaço livre suficiente para o rootfs do contêiner.
- **Backup incompatível** — o formato do arquivo vzdump pode não ser compatível com esta versão do Proxmox.
- **Bridge de rede não encontrada** — a bridge escolhida não existe no nó de destino.

Você pode enviar um novo pacote ou voltar ao painel.
