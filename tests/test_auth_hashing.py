"""Testes do hashing de senha (bcrypt direto, apos a remocao do passlib).

Cobrem o ponto critico da migracao p/ bcrypt 5: compatibilidade com hashes
ja armazenados e o truncamento explicito a 72 bytes.
"""
from api.services.auth import hash_senha, verificar_senha

# Hash no formato $2b$ (identico ao que o passlib/bcrypt 4.x produzia). Garante
# que credenciais ja gravadas continuam validas apos a migracao para bcrypt 5.
_HASH_LEGADO = "$2b$12$n2SbO0EXhvXR6psPLw75QuoGBeD7l1bQrTx8AZytd4xQtEpNZFnye"
_SENHA_LEGADA = "senha-correta-123"


def test_roundtrip_hash_e_verifica():
    h = hash_senha("Minha$enh@Forte1")
    assert h.startswith("$2b$")
    assert verificar_senha("Minha$enh@Forte1", h) is True
    assert verificar_senha("senha-errada", h) is False


def test_compat_com_hash_legado():
    # Hash criado pelo codigo antigo (passlib) ainda valida com o bcrypt direto.
    assert verificar_senha(_SENHA_LEGADA, _HASH_LEGADO) is True
    assert verificar_senha("outra-senha", _HASH_LEGADO) is False


def test_senha_acima_de_72_bytes_trunca_sem_quebrar():
    # bcrypt >= 5 levanta ValueError p/ entradas > 72 bytes; o wrapper trunca.
    base = "a" * 72
    h = hash_senha(base + "-sufixo-ignorado")
    assert verificar_senha(base, h) is True              # mesmos 72 bytes
    assert verificar_senha(base + "-outro", h) is True   # sufixo > 72 ignorado
    assert verificar_senha("a" * 71, h) is False         # 71 bytes != 72


def test_hash_invalido_retorna_false_sem_excecao():
    assert verificar_senha("qualquer", "nao-e-um-hash-bcrypt") is False
    assert verificar_senha("qualquer", "") is False
