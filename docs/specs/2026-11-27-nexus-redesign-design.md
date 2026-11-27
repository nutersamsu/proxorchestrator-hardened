# ProxOrchestrator — redesign "Nexus" (Stitch) · 27/11/2026

## Intenção
Aplicar ao ProxOrchestrator o redesign do projeto Stitch **"ProxOrchestrator Modern UI
Redesign"** (`projects/4008781002491535973`, 28 telas, design system "Nexus Hardened
Cyber-Ops") e **remover o estilo antigo**. O usuário usa o app no homelab (VM própria,
só na rede local) e quer uma interface moderna, densa, escura, tipo console de
operações.

## Decisões do usuário (27/11)
- **Abordagem 1:** novo esqueleto + tema único em cima do Bulma (não trocar por Tailwind,
  não "só cores").
- **Só o tema Nexus.** Somem Classic (sistema/claro/escuro), Ops (sistema/claro/escuro), o
  tema NEXUS antigo, o seletor de tema e o modo claro.
- **Menu nas seções do Stitch, só com páginas reais.** Item do Stitch sem página no app
  fica fora.
- **Só dados reais.** Cartões do Stitch sem fonte de dados (Cyber Defense Posture, eBPF,
  fail2ban, quórum de 3 nós, IOPS, Audit Log, CIS STIG…) ficam fora.
- **Marca própria + logo oficial do Proxmox pequeno** (decidido depois de ler as regras de
  marca da Proxmox, que proíbem usar o logo deles como marca do app): topo do menu = escudo
  + "ProxOrchestrator" em destaque; abaixo, o logo oficial **sem alteração**, menor, com
  "for Proxmox VE" e link para https://www.proxmox.com; rodapé com
  "Proxmox® is a registered trademark of Proxmox Server Solutions GmbH in the EU, the U.S.,
  and other countries." Arquivo do media kit oficial
  (`mediakit-proxmox-server-solutions-logos-*.svg`), guardado em `static/images/proxmox/`.
  A imitação gerada pelo Stitch NÃO é usada.

## Metas
- Visual do Stitch em todas as páginas: canvas `#0B0F19`, cartões de vidro
  `rgba(17,24,39,.75)` + blur 12px + borda 1px `rgba(255,255,255,.05)`, primária ciano
  `#06B6D4` (texto escuro `#0B0F19` no botão), secundária azul `#3B82F6`, sucesso
  `#10B981`, erro `#EF4444`, cantos 4px (ROUND_FOUR), rótulos em JetBrains Mono caixa alta,
  texto Inter. Brilho em vez de sombra. Foco: borda ciano + `0 0 0 2px rgba(6,182,212,.2)`.
- Esqueleto do Stitch: menu lateral 280px com seções; barra de cima com caminho
  (datacenter / nó), busca, chips CPU / RAM ao vivo e atalhos New VM · LXC · Import;
  rodapé do menu com usuário.
- As 132 páginas continuam funcionando (Bulma fica; o CSS novo reestiliza os componentes
  Bulma globalmente).
- Páginas principais com o layout das telas do Stitch, uma por vez.
- Celular: menu vira gaveta < 900px (já existe), alvos ≥ 44px.

## Fora de escopo / não fazer
- Dados inventados, cartões sem fonte, páginas novas que o Stitch "inventou"
  (Security Audit, Disks & Orphans, VM Marketplace como página separada).
- Trocar Bulma por Tailwind; CDN de qualquer tipo (fontes, ícones, Tailwind). O app hoje
  não depende de nada externo e continua assim.
- Mudar comportamento/funções. É redesign visual + organização do menu.
- Deploy na VM 102 sem pedido explícito.

## Mapa do menu (Stitch → páginas reais)
| Seção | Item (texto do Stitch) | Página real |
|---|---|---|
| Datacenter & Cluster | Dashboard | `dashboard` |
| | Nodes & Health | `node_page` (só staff) |
| | VMs & Guests | `inventory` |
| | LXC & Containers | `lxc_list` |
| Storage & Backups | Storage Pools | `datastore_list` |
| | Backup Jobs & Restore | `backups_index` |
| | Export & Import (.px) | `export_index` / `lxc_export_index` (sub-abas) |
| | Import files | `storage_management` |
| Cyber Defense | Firewall & Rules | `firewall_index` |
| | ACME TLS Certs | `cert_settings` |
| Tools & Automation | LXC Store | `lxc_community_scripts` (contador real de scripts) |
| | VM Marketplace | `vm_community_scripts` |
| | Import Disk Wizard | `importer_upload` |
| | Setup Wizard | `wizard` (só staff) |
| System & IAM | Permissions & API | `pveaccess_page` (só staff) |
| | Task History & Logs | `task_list` |
| | Auth & MFA | `auth_settings` + `mfa_setup` |
| | Users | `user_list` |
| | Proxmox · Email | `proxmox_settings`, `email_settings` |
"New VM" e "New Container" saem do menu e viram botões da barra de cima (como no
Stitch). Itens do Stitch sem página: Security Audit, Disks & Orphans → fora.
Rótulos traduzidos em pt-BR (o app tem tradução completa).

## Páginas redesenhadas (ordem = ordem das etapas)
1. **Esqueleto + CSS base** (`base.html`, `proxorchestrator.css` novo, fontes, remoção
   dos temas). Todas as páginas herdam.
2. **Dashboard** (tela "Dashboard (Cluster Overview)"): faixa de status do nó (online,
   uptime, versão PVE, certificado), 4 cartões de métrica (CPU, memória, storage, rede)
   com dados do `/nodes/{node}/status` + RRD já existentes, barra da tarefa ativa (barra de
   tarefas real), tabela de guests com filtros All/VMs/LXCs/Running/Stopped, cartão de
   SMART real (Node → discos), últimas tarefas no lugar do "Audit Log".
3. **VMs & Guests** e **LXC & Containers** (tela "VMs & Guests Inventory").
4. **LXC Store / VM Marketplace** (tela "LXC 1-Click Store").
5. **Firewall & Rules**, **Task History & Logs**, **Storage/Backups**, **Node**,
   **Permissions** (telas correspondentes).
6. **Login / MFA / Setup Wizard** (telas de autenticação e assistente).
As demais páginas (formulários de VM, detalhe de VM, etc.) ficam com o CSS novo sem
mudar o layout; ajustes pontuais se algo ficar quebrado.

## Restrições técnicas
- Bulma 0.9 (vendor) + Font Awesome (vendor) ficam. Ícones: Font Awesome (o Stitch usa
  Material Symbols; troco pelo equivalente FA — chamada minha, evita CDN e 132 templates).
- Fontes: Inter + JetBrains Mono (OFL) em `static/fonts/`, `@font-face` local. Fira sai.
- CSS novo escrito do zero, organizado por tokens (`:root`) → base → componentes Bulma →
  esqueleto → páginas. Sem `[data-theme]`/`[data-skin]`.
- Remover: `THEMES`/`theme_choices` (context_processors), view e rota `/account/theme/`,
  JS de tema do `base.html`, seletor em `wizard/settings.html`, campo
  `UserProfile.ui_theme` (migração nova que remove o campo). `localStorage`
  `proxorchestrator_theme` ignorado.
- Testes atuais (≈215) continuam passando; testes que cobrem tema são atualizados/
  removidos. Testes novos: menu mostra só páginas reais e respeita staff; `/account/theme/`
  responde 404.
- Acessibilidade: contraste ≥ 4.5:1 no texto, foco visível, `prefers-reduced-motion`
  desliga brilho pulsante.
- Tradução: textos novos com `{% translate %}` e entrada no `locale/pt_BR`.

## Verificação
- Testes Django no contêiner descartável (como antes).
- Capturas com Chromium headless contra uma instância de teste com API simulada (o
  token do pve não deve ser usado para testes de escrita); comparar com as telas do Stitch.
- Celular 390px sem rolagem horizontal da página.
- Commit por etapa só após aprovação visual do usuário; deploy na VM 102 só com pedido.

## Abordagens consideradas
1. **Esqueleto novo + tema único sobre Bulma** — escolhida pelo usuário: fiel ao layout do
   Stitch nas páginas principais, mantém 132 páginas funcionando, sem CDN.
2. Copiar HTML do Stitch (Tailwind) — mais fiel ao pixel, mas reescreve tudo de uma vez,
   depende de CDN e arrisca quebrar formulários.
3. Só trocar cores — rápido, mas não chega ao layout do Stitch.

## Regras de marca da Proxmox (media kit, lido em 27/11)
Proibido: usar o logo como representação do app/serviço; alterar o logo ou incorporá-lo à
própria marca; uso enganoso. Permitido: usar o logo menos destacado que o nome do próprio
produto, com link para proxmox.com. O nome do app não pode conter "Proxmox".

## Chamadas minhas (o usuário pode corrigir)
- Chips CPU/RAM da barra de cima usam o mesmo cache de 20 s do resumo do nó.
- Cartão de SMART no dashboard só para staff (como a página Node).
- Ajuda, seletor de idioma e barra de tarefas continuam.
- Font Awesome no lugar de Material Symbols.
- Remover o campo de tema do banco com migração.
- "Audit Log" do Stitch vira "Últimas tarefas" (dado real).
- Atalhos New VM/LXC/Import na barra de cima substituem os itens "New VM"/"New Container".
