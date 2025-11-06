// OpsHub - 프론트엔드 설정
// config.json에서 설정을 로드하여 사용

// 초기값 (config.json이 로드되기 전까지 사용)
let SERVER_HOST = null;
let SERVER_PORT = 8000;
let API_BASE_URL_FROM_CONFIG = null;

// 설정 로드 완료 플래그
let configLoaded = false;

// config.json 로드 함수
async function loadConfig() {
    try {
        // 서버에서 /config.json으로 서빙
        const configPath = '/config.json';
        const response = await fetch(configPath);
        if (response.ok) {
            const config = await response.json();
            console.log('config.json 로드 완료:', config);
            
            if (config.server) {
                SERVER_HOST = config.server.host;
                SERVER_PORT = config.server.http_port || 8000;
                console.log(`서버 설정: ${SERVER_HOST}:${SERVER_PORT}`);
            }
            
            if (config.frontend && config.frontend.api_base_url) {
                API_BASE_URL_FROM_CONFIG = config.frontend.api_base_url;
            } else if (SERVER_HOST) {
                API_BASE_URL_FROM_CONFIG = `http://${SERVER_HOST}:${SERVER_PORT}/api`;
            }
            
            configLoaded = true;
            console.log(`API Base URL: ${API_BASE_URL_FROM_CONFIG}`);
        } else {
            console.error('config.json 로드 실패:', response.status);
        }
    } catch (error) {
        console.error('config.json 로드 실패:', error);
    }
}

// 설정 로드 시작 (즉시 실행)
loadConfig();

