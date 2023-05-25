# functions.inc

finish() {
    exit $1
}

do_prereq() {
    echo "Checking for pre-requisits..."

    # Check if there is python3
    python3 --version 2>&1 > /dev/null
    RES=$?
    if [ ! $RES == 0 ]; then
        echo "[prereq] python3 não encontrado. Saindo"
        exit 1
    fi

    # Check if there is the necessary packages for python
    # google-cloud-monitoring-v3
    pacotes=(google-cloud-monitoring google-cloud-compute)

    for package in ${pacotes[@]}; do
        VER=$(pip3 list | grep $package)
        RES=$?
        if [ ! $RES == 0 ]; then
            echo "[prereq] Não conseguiu encontrar pacote python $package"
            echo "[HINT] tente pip3 install $package"
            exit 1
        fi
    done

    # Check if bash array works
    value="a;b;c;d"
    IFS=';' read -r -a avalue <<< "$value"
    if [ ! ${avalue[1]} == "b" ]; then
        echo "[prereq] Processo de tokenização em array não funciona. Saindo"
        exit 1
    fi

    # Check if exists gcloud
    gcloud --version 2>&1 > /dev/null
    RES=$?
    if [ ! $RES == 0 ]; then
        echo "[prereq] gcloud não encontrado. Saindo"
        exit 1
    fi

    # Check if exists jq
    jq --version 2>&1 > /dev/null
    RES=$?
    if [ ! $RES == 0 ]; then
        echo "[prereq] jq não encontrado. Saindo"
        exit 1
    fi

    # Check if has write permissions to directory outputs
    FILE=outputs/test.temp
    touch $FILE
    RES=$?
    if [ ! $RES == 0 ]; then
        echo "[prereq] Não conseguiu criar arquivo na pasta outputs. Saindo"
        exit 1
    fi

    rm -f $FILE
    RES=$?
    if [ ! $RES == 0 ]; then
        echo "[prereq] Não conseguiu remover arquivo da pasta outputs. Saindo"
        exit 1
    fi

    # Check if can create temporary file
    FILE=`mktemp`
    RES=$?
    if [ ! $RES == 0 ]; then
        echo "[prereq] Não conseguiu criar arquivo temporário com mktemp. SAINDO"
        exit 1
    fi

    rm -f $FILE

    # Retorna OK
    return 0
}