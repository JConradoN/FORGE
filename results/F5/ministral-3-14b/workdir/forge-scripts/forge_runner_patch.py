/** Correção para ID-1: Validação de workdir em exec_run_bash */
    # Validar que workdir está dentro do diretório esperado (evitar traversal)
    workdir_abs = os.path.abspath(workdir)
    if not str(workdir).startswith(str(workdir_abs)):
        return "[ERRO] Caminho de trabalho fora do diretório permitido."