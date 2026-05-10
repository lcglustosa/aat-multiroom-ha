## AAT Multiroom Digital

Integração para Home Assistant do sistema de áudio multiroom **AAT Digital Matrix Amplifiers** (linha PMR-4, PMR-5, PMR-6, PMR-7, PMR-8).

Comunicação via TCP/IP na rede local — sem nuvem, sem latência.

---

### Funcionalidades

**Por zona:**
- Liga / desliga (stand-by)
- Controle de volume (0–87 dB)
- Seleção de entrada (analógica e digital)
- Mute
- Sliders de graves, agudos, balanço e ganho de pré-amp
- Slider de volume no Apple Home via entidade Light (workaround para HomeKit Bridge)

**Dispositivo:**
- Master power (PWRON / PWROFF)
- Ligar / desligar todas as zonas de uma vez (ZTONALL / ZSTDBYALL)
- Mutar / desmutar tudo (MUTEALL / UNMUTEALL)
- Reset remoto via rede

---

### Instalação via HACS

1. Adicione este repositório como **repositório customizado** no HACS (tipo: Integration)
2. Instale **AAT Multiroom Digital**
3. Reinicie o Home Assistant
4. Vá em **Configurações → Integrações → Adicionar integração → AAT Multiroom Digital**

### Configuração manual

Copie a pasta `custom_components/aat_multiroom/` para o diretório `custom_components/` da sua instalação do Home Assistant e reinicie.

---

### Configuração

1. Informe o **IP** do amplificador e a **porta TCP** (padrão: 5000)
2. Informe o **número de zonas** do seu modelo
3. Dê nomes amigáveis para as zonas e entradas

---

### Compatibilidade

| Modelo | Entradas | Zonas |
|--------|----------|-------|
| PMR-4  | 4        | 4     |
| PMR-5  | 4        | 6     |
| PMR-6  | 6        | 4     |
| PMR-7  | 6        | 6     |
| PMR-8  | 5        | 2     |

- Firmware **V1.12 ou superior** recomendado
- Testado no PMR-4

---

### Apple HomeKit

Para usar o controle de volume no **app Casa** do iPhone/iPad:

1. Configure a integração **HomeKit Bridge** no Home Assistant
2. Inclua as entidades `light.aat_*` (não as `media_player.*`) no HomeKit Bridge
3. Cada zona aparecerá como uma lâmpada com slider — o slider de brilho controla o volume

```yaml
# configuration.yaml
homekit:
  - name: AAT Multiroom
    filter:
      include_entities:
        - light.aat_multiroom_sala
        - light.aat_multiroom_quarto
        - switch.aat_multiroom_power
```
