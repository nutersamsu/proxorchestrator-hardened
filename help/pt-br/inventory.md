# Inventário de VMs

O inventário mostra todas as máquinas virtuais do nó Proxmox conectado. Os dados vêm ao vivo da API do Proxmox toda vez que a página é aberta ou atualizada.

## Entendendo a tabela

**VMID** — o número único que o Proxmox usa para a VM.

**Nome** — o nome da VM no Proxmox. Clique para abrir a página de detalhes.

**Estado** — situação de energia:
- Verde "Rodando" — a VM está ligada
- Vermelho "Parado" — a VM está desligada
- Amarelo "Pausada" — a VM está suspensa (o estado da memória é mantido)
- Cinza — estado desconhecido ou em transição

**CPU** — nas VMs rodando, mostra o uso de CPU em porcentagem. Nas paradas, mostra quantos núcleos estão configurados.

**RAM** — a memória máxima da VM. Nas VMs rodando com balloon ativado, a memória realmente usada pode ser menor.

**Tempo ligado** — há quanto tempo a VM está rodando (só nas que estão rodando).

**Nó** — em qual nó do cluster Proxmox a VM está.

## Ações de energia

As ações aparecem conforme o estado da VM:

**VMs rodando:**
- **Desligar** — envia o sinal ACPI do botão de energia ao sistema convidado, que desliga normalmente. Exige que o sistema responda a eventos ACPI (a maioria dos sistemas modernos responde).
- **Forçar parada** — desliga a VM na hora, como puxar o fio da tomada. Sem desligamento normal — use só como último recurso em VMs travadas. Pode corromper o sistema de arquivos se o convidado estava gravando.
- **Reiniciar** — envia o sinal ACPI de reinício. Reinício normal.

**VMs paradas:**
- **Iniciar** — liga a VM.

**VMs pausadas:**
- **Retomar** — tira a VM da pausa/suspensão.

As ações usam HTMX para atualizar só a linha da tabela, sem recarregar a página. A linha mostra o novo estado em 2 a 3 segundos.

## Filtro e busca

Use a caixa de busca para filtrar. Digite parte do nome ou do VMID para filtrar a lista.

## Atualização automática

Marque "Atualização automática" no cabeçalho da página para recarregar a tabela de VMs a cada 30 segundos. Útil para acompanhar as VMs durante manutenções.

## Atualização manual

Clique em "Atualizar" para recarregar na hora a lista de VMs da API do Proxmox.

## Problemas comuns

**A tabela mostra erro ou está vazia** — a API do Proxmox pode estar fora do ar por um momento. Confira o estado da API no painel. Tente atualizar.

**O botão de ação não responde** — a chamada à API pode ter falhado. Confira se o token da API ainda é válido (tokens do Proxmox podem expirar ou ser revogados). Deve aparecer um aviso se a ação falhar.

**A VM mostra o estado errado** — o estado mostrado era o certo na última atualização. Clique em Atualizar para ver os dados atuais. Mudanças feitas pela própria interface do Proxmox só aparecem aqui depois de atualizar.

**VMs de outros nós não aparecem** — hoje o ProxOrchestrator mostra as VMs do nó padrão configurado. O inventário de vários nós está nos planos.
