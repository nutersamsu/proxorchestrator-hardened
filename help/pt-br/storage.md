# Armazenamento

Todos os armazenamentos do nó, com o tipo, o conteúdo que aceitam e o quanto
estão cheios. Clique num armazenamento (ou numa das tags de conteúdo) para
ver o que há nele.

## Tipos de conteúdo

- **Backups**: arquivos do vzdump (as mesmas ações da página Backups).
- **Imagens ISO** e **templates de CT**: mídias de instalação e templates de contêiner.
- **Discos de VM** / **volumes de CT**: imagens de disco dos convidados. Um volume
  cujo convidado não existe mais aparece marcado como *órfão?*.
- **Snippets**, **Import**: hookscripts, snippets do cloud-init, arquivos para importação.

## O que você pode fazer

Os botões só aparecem quando o token da API tem o privilégio:

- excluir imagens ISO, templates e discos órfãos exige `Datastore.Allocate`;
- enviar arquivos ou baixar de uma URL exige `Datastore.AllocateTemplate`
  (e `Sys.Modify` para downloads).

O token recomendado não tem nenhum dos dois, então esses arquivos ficam só
para leitura aqui. Os discos que pertencem a um convidado são gerenciados
pela página da VM ou do contêiner.

*Arquivos de importação* (em Configurações) é outra página: ela gerencia os
arquivos enviados ao ProxOrchestrator para importar VMs.
