"""Relógio do app. O modo Admin pode ADIANTAR a data (simulação de dias/meses/anos) sem mexer no relógio do sistema:
todos os módulos usam clock.today() em vez de date.today()."""
from datetime import date, timedelta
_offset = 0

def set_offset(n): global _offset; _offset = int(n)
def offset(): return _offset
def today(): return date.today() + timedelta(days=_offset)
