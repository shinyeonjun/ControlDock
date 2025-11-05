// OpsHub - 프론트엔드 설정

// 기본값
let SERVER_HOST = '172.24.194.92';
let SERVER_PORT = 8000;
let API_BASE_URL_FROM_CONFIG = `http://${SERVER_HOST}:${SERVER_PORT}/api`;

// 루트 config.json에서 설정 로드
(async function loadConfig() {
    try {
        // 서버에서 /config.json으로 서빙
        const configPath = '/config.json';
        const response = await fetch(configPath);
        if (response.ok) {
            const config = await response.json();
            if (config.server) {
                SERVER_HOST = config.server.host || SERVER_HOST;
                SERVER_PORT = config.server.http_port || SERVER_PORT;
            }
            if (config.frontend && config.frontend.api_base_url) {
                API_BASE_URL_FROM_CONFIG = config.frontend.api_base_url;
            } else {
                API_BASE_URL_FROM_CONFIG = `http://${SERVER_HOST}:${SERVER_PORT}/api`;
            }
        }
    } catch (error) {
        console.log('config.json 로드 실패, 기본값 사용:', error);
    }
})();

