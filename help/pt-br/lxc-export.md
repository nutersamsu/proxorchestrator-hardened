# Exportar e importar contêineres

Esta página é a central dos pacotes `.px` de contêiner — arquivos portáteis que permitem levar contêineres LXC entre servidores Proxmox que usam o ProxOrchestrator.

## Exportar um contêiner

Para exportar um contêiner:
1. Vá em **Inventário de contêineres** e clique no nome de um contêiner para abrir os detalhes
2. Clique em **Exportar contêiner** no cabeçalho da página
3. Confirme a exportação — ela começa na hora

A exportação usa o `vzdump` do Proxmox em **modo snapshot**, então o contêiner continua rodando, sem parada, durante o processo. O pacote `.px` exportado contém o rootfs completo do contêiner e os metadados de configuração.

### Tabela de exportações

A tabela mostra os jobs de exportação recentes com o estado de cada um:
- **Concluído** — pronto para baixar. Clique em Baixar para salvar o arquivo `.px`.
- **Em andamento** — clique em Ver andamento para acompanhar as etapas em tempo real.
- **Falhou** — a exportação teve um erro.

As exportações concluídas são **apagadas automaticamente depois de 24 horas** (`EXPORT_RETENTION_HOURS` no `.env`), ou logo depois de um download completo quando *Remover o pacote deste servidor logo depois do download* estiver marcado (o padrão).

Você pode excluir qualquer job de exportação pelo ícone da lixeira.

## Importar um contêiner

Para importar um contêiner de um pacote `.px` exportado por outra instância do ProxOrchestrator:

1. Clique em **Importar pacote de contêiner** no cabeçalho da página (ou use o cartão de envio à direita)
2. Envie o arquivo `.px`
3. Revise e ajuste as configurações do contêiner (nome, recursos, rede, armazenamento)
4. Clique em Implantar para criar o contêiner no seu nó Proxmox

### Tabela de importações

As importações recentes aparecem abaixo da tabela de exportações, com o estado de cada uma. As concluídas têm o link **Ver contêiner**, que leva direto à página do novo contêiner.

## Usos

- **Migrar contêineres** entre clusters ou nós Proxmox
- **Guardar configurações de contêineres** sem depender do backup embutido do Proxmox
- **Compartilhar ambientes de desenvolvimento** com a equipe
- **Recuperação de desastres** — manter cópias portáteis de contêineres importantes

## Observações importantes

- Só são aceitos para importação pacotes `.px` exportados pelo ProxOrchestrator
- O contêiner importado recebe um novo CTID (automático ou escolhido por você)
- As configurações de rede (bridge, IP) devem ser ajustadas ao ambiente de destino
- Os dados do contêiner (arquivos dentro do rootfs) ficam exatamente como foram exportados
