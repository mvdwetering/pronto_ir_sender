# Pronto IR Sender

A [Home Assistant](https://www.home-assistant.io/) custom integration that exposes a `remote` entity for sending raw [Pronto hex](http://www.remotecentral.com/features/irdisp2.htm) IR codes via the Home Assistant [infrared entity platform](https://developers.home-assistant.io/docs/core/entity/infrared/).

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

## Requirements

- Home Assistant with the `infrared` domain available (introduced in 2026.4)
- An infrared emitter integration already set up (e.g. ESPHome, Unfolded Circle remote)

## Installation

### HACS (recommended)

1. In HACS, go to **Integrations → ⋮ → Custom repositories**
2. Add `https://github.com/mvdwetering/pronto_ir_sender` with category **Integration**
3. Install **Pronto IR Sender** from HACS
4. Restart Home Assistant

### Manual

Copy the `custom_components/pronto_ir_sender` folder into your Home Assistant `config/custom_components/` directory and restart.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Pronto IR Sender**
3. Select the infrared transmitter entity to use (e.g. your ESPHome IR blaster)

A `remote` entity is created for the selected transmitter.

## Usage

Use the `remote.send_command` action to send a raw Pronto hex code:

```yaml
action: remote.send_command
target:
  entity_id: remote.pronto_ir_sender
data:
  command: "0000 006C 0022 0002 015B 00AD 0016 0016 0016 0041 0016 0016 0016 0041 0016 0041 0016 0041 0016 0041 0016 0016 0016 0041 0016 0016 0016 0016 0016 0016 0016 0016 0016 0041 0016 0016 0016 0041 0016 0016 0016 0016 0016 0041 0016 0041 0016 0016 0016 0016 0016 0016 0016 0041 0016 0041 0016 0041 0016 0041 0016 0016 0016 0016 0016 0041 0016 0041 0016 0016 0016 06FB"
```

Multiple codes and repeat options are supported:

```yaml
action: remote.send_command
target:
  entity_id: remote.pronto_ir_sender
data:
  command:
    - "0000 006C ..."   # first code
    - "0000 006C ..."   # second code
  num_repeats: 3        # send the full sequence 3 times
  delay_secs: 0.5       # wait 0.5 s between repetitions
```

### Pronto hex format

Only **raw Pronto codes** (type `0000`) are supported. These are space-separated 4-digit hex words:

```
0000 <freq> <n1> <n2> <mark> <space> … [n1 pairs] <mark> <space> … [n2 pairs]
```

| Field | Description |
|-------|-------------|
| `0000` | Raw format indicator |
| `freq` | Carrier frequency code (actual Hz ≈ 1 000 000 / (freq × 0.241246)) |
| `n1` | Number of mark/space pairs in the "once" sequence |
| `n2` | Number of mark/space pairs in the optional repeat sequence |

Raw Pronto codes can be found on [Remote Central](http://www.remotecentral.com/) or exported from tools like [IrScrutinizer](https://github.com/bengtmartensson/IrScrutinizer).
