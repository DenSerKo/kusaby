document.getElementById('saby-auth').addEventListener('click', () => {
    const baseUrl = 'https://fix-online.sbis.ru/oauth/api/token';

    const randomState = crypto.randomUUID();
    sessionStorage.setItem('sbis_oauth_state', randomState);

    // Собираем параметры запроса (URLSearchParams сам закодирует redirect_uri)
    const params = new URLSearchParams({
      client_id: '5008322050105118',
      response_type: 'code',
      state: randomState,
      redirect_uri: 'http://127.0.0.1:8000/'
    });

    const fullAuthUrl = `${baseUrl}?${params.toString()}`;

    // Открываем окно strictly внутри обработчика click
    window.open(
      fullAuthUrl,
      'Подключение к СБИС',
      'width=600,height=700,scrollbars=1,toolbar=0'
    );
  });