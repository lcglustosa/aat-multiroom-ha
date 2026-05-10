# AAT Multiroom Digital — integração para Home Assistant

Integração custom (não-oficial) que conecta os amplificadores **AAT Digital Matrix** (linha PMR-4/5/6/7/8) ao **Home Assistant** via TCP, e por extensão à **Alexa** quando você usa o Home Assistant Cloud (Nabu Casa).

Cada zona vira uma entidade `media_player` no HA com:

- Liga / desliga (entra/sai de stand-by por zona)
- Volume (set, +, -, mute)
- Seleção de fonte (Entrada 1–6, com nomes amigáveis)

A integração usa apenas comandos documentados na *AAT Digital Matrix Amplifiers API Rev.10*.

---

## Requisitos

- AAT da linha PMR com firmware ≥ V1.12 (o que tem porta TCP). PMR-4 testado.
- Home Assistant Core / OS / Container (qualquer um) ≥ 2024.4.
- AAT acessível via rede do HA (mesma LAN ou rota TCP).
- **IP fixo no AAT** — recomendado fortemente. Use o menu de instalação do AAT ou uma reserva DHCP no roteador.
- (Opcional, para Alexa) Assinatura Nabu Casa (~US$ 6,50/mês).

---

## Instalação

Esta integração ainda não está no HACS. Por enquanto, instale manualmente:

1. Encontre a pasta `config` do seu Home Assistant. É a mesma pasta onde está o `configuration.yaml`.
2. Dentro dela, crie (se ainda não existir) a pasta `custom_components/`.
3. Copie a pasta `custom_components/aat_multiroom/` deste repositório para lá. A estrutura final fica:

   ```
   <config>/
   └── custom_components/
       └── aat_multiroom/
           ├── __init__.py
           ├── aat_protocol.py
           ├── config_flow.py
           ├── const.py
           ├── coordinator.py
           ├── manifest.json
           ├── media_player.py
           ├── strings.json
           └── translations/
               ├── en.json
               └── pt-BR.json
   ```

4. Reinicie o Home Assistant.

---

## Configuração no Home Assistant

1. **Configurações → Dispositivos e Serviços → Adicionar integração**.
2. Procure por **AAT Multiroom Digital**.
3. Preencha:
   - **Endereço IP** do AAT (ex: `192.168.1.50`).
   - **Porta TCP**: 5000 (padrão da AAT — só altere se você configurou a porta secundária).
   - **Número de zonas**: 4 para o PMR-4, 6 para PMR-5/7, 2 para PMR-8.
4. Se a conexão der certo, o HA vai pedir os **nomes amigáveis** para cada zona (ex: "Sala", "Cozinha", "Quarto", "Varanda") e para cada entrada (ex: "Spotify", "TV"). Deixe em branco as entradas que você não usa.
5. Após salvar, aparecerá um dispositivo **AAT Multiroom (<ip>)** com uma entidade `media_player.<nome_da_zona>` para cada zona.

Para editar nomes depois: **Configurações → Dispositivos e Serviços → AAT Multiroom → Configurar**.

---

## Conectando à Alexa via Nabu Casa

1. No HA: **Configurações → Home Assistant Cloud** e ative a integração com Alexa.
2. Em **Entidades expostas**, marque os `media_player` de cada zona.
3. No app Alexa: **Dispositivos → +** → procure por novos dispositivos. As zonas aparecem como alto-falantes.
4. (Opcional, recomendado) Coloque cada zona em um **Cômodo/Grupo** correspondente no app Alexa, pra dar contexto à voz ("Alexa, desliga aqui").

### Exemplos de comandos de voz

| Comando | O que faz |
| --- | --- |
| "Alexa, ligar a Sala" | `ZSTDBYOFF` na zona Sala |
| "Alexa, desligar a Cozinha" | `ZSTDBYON` na zona Cozinha |
| "Alexa, volume do Quarto em 30%" | `VOLSET` zona Quarto = ~26 (30% de 87) |
| "Alexa, aumentar o volume da Sala" | `VOL+` na zona Sala |
| "Alexa, mutar a Varanda" | `MUTEON` na zona Varanda |

A troca de fonte por voz na Alexa é limitada ao comando "trocar entrada" pra alguns alto-falantes — se não funcionar diretamente, crie uma **Rotina Alexa** que aciona o serviço `media_player.select_source` no HA.

---

## Apple Home (HomeKit Bridge)

A integração já vem com `device_class = SPEAKER` em cada zona, então o HomeKit Bridge do HA expõe naturalmente cada zona como **alto-falante** na Casa (e não como TV, que é o default do HA pra `media_player` e fica esquisito).

### Setup

1. Confirme que a integração **HomeKit Bridge** já está adicionada no HA (Configurações → Dispositivos e Serviços → HomeKit Bridge). Você já tem isso.
2. Em **Entidades** da bridge, marque os `media_player.<sua_zona>` que você quer ver na Casa. Se a bridge estiver em modo "Filter", garanta que `media_player` esteja no domínio incluído ou que cada entidade esteja explicitamente listada.
3. Para que a Casa pegue as mudanças, você pode precisar **resetar** a bridge depois de adicionar entidades novas: Configurações → Dispositivos → HomeKit Bridge → vai no menu de três pontos → **Reset Accessory**. Reemparelhe pelo app Casa (escaneando o QR code que o HA mostra).
4. No app **Casa**: as zonas aparecem como acessórios de áudio. Atribua cada uma ao cômodo certo (Sala, Cozinha, etc.) pra ter contextos do tipo "ei Siri, desliga aqui".

### O que funciona via Casa / Siri

| Ação | No app Casa | Por voz |
| --- | --- | --- |
| Ligar/desligar zona | Toque no botão de power | "Ei Siri, ligar a Sala" |
| Volume | Slider no card da zona | "Ei Siri, volume da Cozinha em 40%" |
| Trocar fonte | Tocar e segurar o card → seleciona | "Ei Siri, mudar a Sala para Spotify" (depende da versão do iOS) |
| Mute | Slider no zero ou ação custom em automação | — |

Apple Home não tem comando de voz nativo pra trocar fonte de speaker em todas as versões do iOS. Se a Siri não obedecer "mudar para X", o caminho que sempre funciona é criar uma **automação ou cena** na Casa que dispare o serviço `media_player.select_source` via HA — você cria a cena uma vez no HA, expõe via HomeKit, e dispara por voz pelo nome dela.

### Cenas úteis

Sugestão de cenas pra criar no HA e expor via HomeKit Bridge:

- **"Música em todo lugar"** — liga as 4 zonas com mesma fonte e volume médio.
- **"Modo cinema"** — desliga zonas que não são a Sala, baixa o volume da Sala.
- **"Boa noite"** — desliga todas as zonas (`ZSTDBYALL` no AAT, ou um por um pelo HA).

Cada cena vira um botão na Casa e responde a "ei Siri, música em todo lugar".

### Limitações conhecidas no Apple Home

- A Casa pode demorar 5–30 s pra refletir mudanças feitas pelo controle remoto do AAT (poll do HA é a cada 30 s).
- Se você adicionar mais zonas/entidades depois, talvez precise resetar a bridge HomeKit pra Casa enxergar — ou aguardar refresh.
- Source select via Siri é flaky historicamente; cenas são o plano B confiável.

---

## Como funciona por dentro (resumo técnico)

- **Protocolo**: TCP na porta 5000, mensagens ASCII no formato `[t<seq> <CMD> <par1> <par2>]`. Ver `aat_protocol.py`.
- **Polling**: A cada 30 s o coordinator manda `GETALL` (pega tudo de uma vez) + `ZSTDBYGET` por zona (porque o GETALL não traz stand-by).
- **Comandos**: Disparados imediatamente pela UI/Alexa, seguidos de um refresh do coordinator pra UI ficar sincronizada.
- **Conexão única**: Uma `AatClient` é compartilhada por todas as entidades, com lock pra serializar requests (o AAT só responde a um comando por vez).

### Mapeamentos importantes

| HA `media_player` | Comando AAT |
| --- | --- |
| `turn_on` | `ZSTDBYOFF <zona>` (e `PWRON` se o aparelho todo estiver desligado) |
| `turn_off` | `ZSTDBYON <zona>` |
| `volume_set` (0.0–1.0) | `VOLSET <zona> <0–87>` |
| `volume_up` / `volume_down` | `VOL+` / `VOL-` |
| `volume_mute(true/false)` | `MUTEON` / `MUTEOFF` |
| `select_source` | `INPSET <zona> <1–6>` |

---

## Troubleshooting

**"Couldn't reach the AAT at that address"** durante o setup
: Verifique se o IP está correto, se o AAT está ligado e se a porta 5000 está aberta na rede. Teste com `nc -zv <ip> 5000` no terminal.

**Estado errado / atrasado no HA**
: O AAT não notifica mudanças, então a UI pode levar até 30 s pra refletir uma alteração feita pelo controle remoto/painel frontal. Se quiser refresh mais rápido, edite `DEFAULT_SCAN_INTERVAL` em `const.py`.

**Aparelho fica "desligado" no HA mesmo estando ligado**
: O comando `PWRGET` retorna o status global. Se o switch traseiro estiver desligado o produto não responde a nada. Confira o LED frontal: vermelho = stand-by, azul = ligado.

**Comando não funciona**
: Habilite logs detalhados em `configuration.yaml`:
  ```yaml
  logger:
    default: info
    logs:
      custom_components.aat_multiroom: debug
  ```
  Depois reinicie e veja os logs em **Configurações → Sistema → Logs**.

---

## Limitações conhecidas

- **Não há push de eventos**: o AAT só envia mensagem espontânea no `POWERDOWN` (queda de energia). Mudanças via controle remoto/IR aparecem só no próximo poll.
- **Bass / Treble / Balance / Pre-amp** não estão expostos como controles HA — só são lidos pelo `GETALL`. Se quiser controlar via HA, dá pra estender `media_player.py` com `extra_state_attributes` + um service custom.
- **Modo MONO / STEREO / BRIDGE** das zonas não é exposto. Configure via painel frontal do AAT.
- **Comandos não disponíveis por automação** (item 13 do PDF da AAT) seguem inacessíveis — eles só funcionam pelo painel frontal do AAT.

---

## Testando o protocolo localmente (sem o HA)

Antes de publicar no HA, dá pra exercitar o parser/encoder com:

```
python3 tests/test_protocol.py
```

Ele valida codificação de comandos, parsing de respostas e o `GETALL` usando os exemplos do datasheet.

---

## Licença

MIT — veja `LICENSE`. Esta integração não é endorsed nem suportada oficialmente pela Advanced Audio Technologies.
