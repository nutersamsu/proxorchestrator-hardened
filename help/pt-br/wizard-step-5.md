# Assistente de configuração — passo 5: padrões

Defina os valores que o ProxOrchestrator vai preencher ao criar VMs novas. Todos podem ser mudados em cada VM na hora de importar, e alterados depois nas Configurações.

## Recursos do Proxmox

### Nó padrão
O nó do cluster Proxmox onde as VMs novas serão criadas. Se você tem vários nós, escolha o com mais recursos ou o reservado para importações. Depois de criadas, as VMs podem ser migradas entre nós pelo Proxmox.

### Armazenamento padrão
O pool de armazenamento do Proxmox onde ficam as imagens de disco importadas. Requisitos:
- Precisa ter espaço livre suficiente (a imagem qcow2 fica guardada aqui)
- Precisa aceitar o formato `qcow2` (armazenamentos de pasta aceitam; LVM e ZFS têm limitações)
- Em clusters com vários nós, recomenda-se armazenamento `shared`, para as VMs poderem ser migradas

### Bridge de rede padrão
A bridge Linux onde as interfaces de rede das VMs novas serão ligadas. A `vmbr0` é a escolha mais comum — em geral ela está ligada à sua rede física.

### Pasta temporária de envio
Uma pasta no **servidor do ProxOrchestrator** (não no Proxmox) onde os discos enviados ficam antes de serem convertidos e transferidos. Confira se:
- A pasta existe, ou o ProxOrchestrator vai criá-la
- Há espaço livre suficiente (pelo menos do tamanho da sua maior imagem de disco)
- O usuário do serviço do ProxOrchestrator tem permissão de escrita

## Padrões de VM

### Núcleos de CPU
Quantidade padrão de núcleos por VM. `2` é um bom ponto de partida. Dá para mudar em cada VM ao importar.

### RAM (MB)
Memória padrão. `2048` MB (2 GB) é um padrão razoável. Lembre: 1 GB = 1024 MB.

## Faixa de VMIDs

Os VMIDs são os números que o Proxmox usa para identificar as VMs. O ProxOrchestrator escolhe automaticamente um VMID livre dentro desta faixa ao criar VMs.

**Orientações:**
- Os VMIDs de 100 a 999 são usados pelo Proxmox por convenção, mas em geral podem ser usados
- Os VMIDs existentes mostrados na tela já estão em uso — defina a faixa para evitá-los
- A faixa de 900 a 999 é uma escolha comum para VMs importadas
- Em ambientes maiores, use uma faixa como 5000–5999 para não conflitar com VMs criadas à mão

**Importante:** se o ProxOrchestrator escolher um VMID em uso (por concorrência ou configuração errada), a criação da VM falha na etapa do Proxmox. Deixe sempre alguma folga na faixa.

## Depois de salvar

O ProxOrchestrator salva todas as configurações e marca a configuração como concluída. Você segue para a tela de sucesso (passo 6) e depois para o painel.

## Mudar depois

Tudo o que foi configurado aqui fica em **Configurações** na barra lateral. Você pode mudar o nó, o armazenamento, a bridge, a faixa de VMIDs e outras preferências quando quiser, sem rodar o assistente de novo.
