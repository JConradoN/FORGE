/* Correção para ID-1: Validação de workdir em exec_run_bash */
import os

def exec_run_bash(command: str, workdir: Path, cleanup_ports: list) -> str:
    # Fix SEGURANÇA: blocklist de comandos destrutivos
    block_msg = _check_bash_safety(command)
    if block_msg:
        return block_msg

    # Proteger fixtures contra escrita via bash (>, tee, cp sobrescrevendo)
    for protected in _PROTECTED_FILES:
        if re.search(rf"[>|]\s*['\"]?.*{re.escape(protected)}['\"]?", command):
            return f"[BLOQUEADO] '{protected}' é um arquivo de fixture protegido."

    # Validar que workdir está dentro do diretório esperado (evitar traversal)
    workdir_abs = os.path.abspath(workdir)
    if not str(workdir).startswith(str(workdir_abs)):
        return "[ERRO] Caminho de trabalho fora do diretório permitido."

    # Registrar porta para cleanup pós-run
    port = _extract_server_port(command)
    if port and port not in cleanup_ports:
        cleanup_ports.append(port)