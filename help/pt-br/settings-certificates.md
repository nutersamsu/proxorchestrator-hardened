# Gerenciamento de certificados

O ProxOrchestrator mostra a interface web por HTTPS. Nesta página você vê o certificado TLS atual e pode trocá-lo por um seu.

## Informações do certificado atual

O painel de detalhes mostra:
- **Assunto (Subject)** — o Common Name (CN) do certificado, normalmente o nome ou o IP para o qual ele foi emitido
- **Emissor** — quem assinou o certificado. "Autoassinado" significa que ele assinou a si mesmo (comum em ferramentas internas). Um nome de CA significa que ele foi emitido por uma autoridade certificadora.
- **Válido desde / até** — o período de validade. A data de expiração tem cores:
  - **Verde** — faltam mais de 30 dias
  - **Laranja/amarelo** — faltam menos de 30 dias — planeje a renovação
  - **Vermelho** — expirado — os navegadores vão mostrar avisos de segurança a todos

## Certificado autoassinado ou assinado por CA

**Certificados autoassinados** (o padrão) são gerados automaticamente na instalação. Eles criptografam a conexão, mas os navegadores mostram o aviso "Sua conexão não é particular", porque o certificado não foi assinado por uma CA confiável. Cada usuário precisa aceitar o aviso.

**Certificados assinados por CA** de uma autoridade confiável (Let's Encrypt, DigiCert, a PKI interna da empresa etc.) são aceitos pelos navegadores sem aviso. Muito recomendado em produção.

## Trocar o certificado

Envie os dois:
1. **Arquivo do certificado** — certificado em PEM, de preferência com a cadeia completa (certificado do servidor + intermediários). Extensões: `.pem`, `.crt`, `.cer`
2. **Arquivo da chave privada** — chave privada RSA ou ECDSA em PEM. A chave precisa corresponder ao certificado. Extensões: `.pem`, `.key`

**Requisitos importantes:**
- A chave privada NÃO pode ter senha (passphrase)
- Só formato PEM (não DER/binário)
- O certificado precisa cobrir o nome que os usuários usam para acessar o ProxOrchestrator

Depois do envio, o ProxOrchestrator valida o par certificado/chave e recarrega o nginx. Pode ser preciso esperar 5 a 10 segundos e recarregar a página.

## Certificado grátis do Let's Encrypt

A forma mais simples é a aba **Automação de certificados (ACME)**: ela emite e renova o certificado sozinha (desafio HTTP-01 com a porta 80 aberta para a internet, ou DNS-01 em redes privadas).

Se preferir fazer à mão e o servidor for acessível pela internet:

```
certbot certonly --standalone -d proxorchestrator.seudominio.com
```

O certificado e a chave ficam em `/etc/letsencrypt/live/proxorchestrator.seudominio.com/`. Use:
- `fullchain.pem` como arquivo do certificado (inclui a cadeia)
- `privkey.pem` como arquivo da chave privada

Os certificados do Let's Encrypt valem 90 dias. Configure a renovação automática com `certbot renew` num cron.

## PKI interna / Active Directory Certificate Services

Se a sua empresa tem uma CA própria (comum em ambientes corporativos):
1. Peça um certificado para o nome do servidor do ProxOrchestrator (ou use a aba **Gerar CSR**)
2. Exporte o certificado e a chave privada em PEM
3. Envie aqui

Confira se as CAs raiz e intermediária são confiáveis nos navegadores dos usuários (em ambientes de domínio normalmente já são, por GPO).

## Gerar um novo certificado autoassinado

Clique em "Gerar novo certificado autoassinado" para criar um certificado autoassinado novo. É útil quando o atual expirou. O novo certificado vale por 10 anos.

## Nome/IP que o certificado não cobre

Se os usuários acessam o ProxOrchestrator pelo IP, mas o Subject do certificado só cobre o nome (ou o contrário), os navegadores mostram um aviso. Confira se os nomes alternativos (SANs) do certificado incluem todos os nomes e IPs usados para acessar.

## Problemas comuns

**O certificado e a chave não correspondem** — o ProxOrchestrator confere isso antes de salvar. Se não corresponderem, aparece um erro. Envie a chave privada que corresponde ao certificado enviado.

**"O certificado não é válido para este nome"** — o certificado foi emitido para outro nome. Peça um certificado para o nome certo ou acrescente o nome atual como SAN.

**O nginx não recarrega depois do envio** — confira os logs do ProxOrchestrator. O certificado ou a chave podem ter formatação inválida mesmo parecendo certos. Tente converter com `openssl x509 -in cert.crt -out cert.pem` e `openssl rsa -in key.key -out key.pem`.
