"""Limites direccionales por ENT1-ENT3, independientes del indice del encoder."""

LIMIT_NEGATIVE = 1
LIMIT_POSITIVE = 2


def blocked_direction(value, mask):
    if value < 0 and mask & LIMIT_NEGATIVE:
        return LIMIT_NEGATIVE
    if value > 0 and mask & LIMIT_POSITIVE:
        return LIMIT_POSITIVE
    return 0


class TravelLimits:
    def __init__(self, pins, roles, active_levels):
        if len(pins) != 3 or len(roles) != 3 or len(active_levels) != 3:
            raise ValueError('Configurar exactamente ENT1, ENT2 y ENT3')
        if any(type(role) is not int or role not in (-1, 0, 1) for role in roles):
            raise ValueError('Rol de limite: -1 negativo, 0 general, 1 positivo')
        if any(type(level) is not int or level not in (0, 1) for level in active_levels):
            raise ValueError('Nivel activo de limite: 0 o 1')
        self.pins = pins
        self.roles = tuple(roles)
        self.active_levels = tuple(active_levels)
        self.enabled = any(roles)
        self.mask = self.active_inputs = 0

    def sample(self):
        if not self.enabled:
            return 0
        mask = active = 0
        for i in range(3):
            role = self.roles[i]
            if role and self.pins[i].value() == self.active_levels[i]:
                active |= 1 << i
                mask |= LIMIT_NEGATIVE if role < 0 else LIMIT_POSITIVE
        self.mask, self.active_inputs = mask, active
        return mask
