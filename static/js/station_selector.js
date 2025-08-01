// static/js/station_selector.js

// 페이지 로드 시 초기화 (API 호출 제거)
document.addEventListener('DOMContentLoaded', function() {
    initializeStationSelector();
    // loadStationStatistics(); // 제거 - 불필요한 API 호출
});

function initializeStationSelector() {
    // 키보드 단축키 설정
    document.addEventListener('keydown', function(e) {
        // 숫자키 1-9로 충전소 선택
        if (e.key >= '1' && e.key <= '9') {
            const index = parseInt(e.key) - 1;
            const cards = document.querySelectorAll('.station-card');
            if (cards[index]) {
                cards[index].click();
            }
        }
        
        // ESC키로 첫 번째 충전소 선택
        if (e.key === 'Escape') {
            const firstCard = document.querySelector('.station-card');
            if (firstCard) {
                firstCard.click();
            }
        }
    });
    
    // 카드 호버 효과 개선
    const stationCards = document.querySelectorAll('.station-card');
    stationCards.forEach((card, index) => {
        // 마우스 진입 시
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-8px) scale(1.02)';
            this.style.zIndex = '10';
        });
        
        // 마우스 이탈 시
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
            this.style.zIndex = '1';
        });
        
        // 클릭 시 애니메이션
        card.addEventListener('click', function(e) {
            // 버튼 클릭이 아닌 경우만 처리
            if (!e.target.closest('.btn')) {
                this.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    this.style.transform = 'scale(1)';
                }, 150);
            }
        });
        
        // 순차적 애니메이션을 위한 지연 설정
        card.style.animationDelay = `${index * 0.1}s`;
    });
    
    // 툴팁 기능 추가
    addTooltips();
    
    // 검색 기능 추가
    addSearchFunctionality();
}

function addTooltips() {
    const stationCards = document.querySelectorAll('.station-card');
    stationCards.forEach(card => {
        const stationName = card.querySelector('.station-name').textContent;
        const stationLocation = card.querySelector('.station-location').textContent;
        
        card.setAttribute('title', `${stationName}\n${stationLocation}\n클릭하여 대시보드로 이동`);
    });
}

function addSearchFunctionality() {
    // 검색 입력 필드 생성
    const header = document.querySelector('.header');
    const searchContainer = document.createElement('div');
    searchContainer.className = 'search-container';
    searchContainer.innerHTML = `
        <input type="text" id="station-search" placeholder="충전소 이름 또는 지역으로 검색..." />
        <div class="search-icon">🔍</div>
    `;
    
    // 검색 스타일 추가
    const searchStyle = document.createElement('style');
    searchStyle.textContent = `
        .search-container {
            position: relative;
            max-width: 400px;
            margin: 20px auto 0;
        }
        
        #station-search {
            width: 100%;
            padding: 12px 40px 12px 15px;
            border: none;
            border-radius: 25px;
            background: rgba(255,255,255,0.2);
            color: white;
            font-size: 1em;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.3);
        }
        
        #station-search::placeholder {
            color: rgba(255,255,255,0.7);
        }
        
        #station-search:focus {
            outline: none;
            background: rgba(255,255,255,0.3);
            border-color: rgba(255,255,255,0.5);
        }
        
        .search-icon {
            position: absolute;
            right: 15px;
            top: 50%;
            transform: translateY(-50%);
            color: rgba(255,255,255,0.7);
        }
        
        .station-card.hidden {
            display: none;
        }
        
        .no-results {
            text-align: center;
            padding: 40px;
            color: #666;
            font-size: 1.2em;
        }
    `;
    document.head.appendChild(searchStyle);
    
    header.appendChild(searchContainer);
    
    // 검색 기능 구현
    const searchInput = document.getElementById('station-search');
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase().trim();
        const stationCards = document.querySelectorAll('.station-card');
        let visibleCount = 0;
        
        stationCards.forEach(card => {
            const stationName = card.querySelector('.station-name').textContent.toLowerCase();
            const stationLocation = card.querySelector('.station-location').textContent.toLowerCase();
            const regionBadge = card.querySelector('.region-badge').textContent.toLowerCase();
            
            const isMatch = stationName.includes(searchTerm) || 
                           stationLocation.includes(searchTerm) || 
                           regionBadge.includes(searchTerm);
            
            if (isMatch || searchTerm === '') {
                card.classList.remove('hidden');
                visibleCount++;
            } else {
                card.classList.add('hidden');
            }
        });
        
        // 검색 결과가 없는 경우 메시지 표시
        const stationsGrid = document.querySelector('.stations-grid');
        let noResultsMsg = document.querySelector('.no-results');
        
        if (visibleCount === 0 && searchTerm !== '') {
            if (!noResultsMsg) {
                noResultsMsg = document.createElement('div');
                noResultsMsg.className = 'no-results';
                noResultsMsg.innerHTML = `
                    <div>🔍 검색 결과가 없습니다</div>
                    <div style="font-size: 0.9em; margin-top: 10px; color: #999;">
                        다른 키워드로 검색해보세요
                    </div>
                `;
                stationsGrid.appendChild(noResultsMsg);
            }
        } else {
            if (noResultsMsg) {
                noResultsMsg.remove();
            }
        }
    });
    
    // 엔터키로 첫 번째 검색 결과 선택
    searchInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            const firstVisibleCard = document.querySelector('.station-card:not(.hidden)');
            if (firstVisibleCard) {
                firstVisibleCard.click();
            }
        }
    });
}

// 사용하지 않는 함수들 제거 또는 간소화
function showSimpleMessage(message, type = 'info') {
    const header = document.querySelector('.header');
    const messageDiv = document.createElement('div');
    messageDiv.className = `simple-message ${type}`;
    messageDiv.textContent = message;
    
    const messageStyle = document.createElement('style');
    messageStyle.textContent = `
        .simple-message {
            background: rgba(255,255,255,0.9);
            color: #333;
            padding: 10px 20px;
            border-radius: 20px;
            margin: 10px auto;
            max-width: 400px;
            text-align: center;
            font-size: 0.9em;
        }
        .simple-message.info { border-left: 4px solid #2196f3; }
        .simple-message.error { border-left: 4px solid #f44336; }
        .simple-message.success { border-left: 4px solid #4caf50; }
    `;
    document.head.appendChild(messageStyle);
    
    header.appendChild(messageDiv);
    
    // 3초 후 자동 제거
    setTimeout(() => {
        messageDiv.remove();
    }, 3000);
}

// 터치 디바이스 지원
if ('ontouchstart' in window) {
    document.querySelectorAll('.station-card').forEach(card => {
        card.addEventListener('touchstart', function() {
            this.style.transform = 'translateY(-4px) scale(1.01)';
        });
        
        card.addEventListener('touchend', function() {
            setTimeout(() => {
                this.style.transform = 'translateY(0) scale(1)';
            }, 150);
        });
    });
}

// 접근성 향상
document.addEventListener('keydown', function(e) {
    // Tab 키 네비게이션 개선
    if (e.key === 'Tab') {
        const focusableElements = document.querySelectorAll(
            '.station-card, .btn, input, a[href]'
        );
        const currentIndex = Array.from(focusableElements).indexOf(document.activeElement);
        
        if (e.shiftKey) {
            // Shift + Tab (이전 요소)
            if (currentIndex > 0) {
                e.preventDefault();
                focusableElements[currentIndex - 1].focus();
            }
        } else {
            // Tab (다음 요소)
            if (currentIndex < focusableElements.length - 1) {
                e.preventDefault();
                focusableElements[currentIndex + 1].focus();
            }
        }
    }
});

// 성능 최적화: Intersection Observer로 카드 애니메이션
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const cardObserver = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// 페이지 로드 완료 후 관찰 시작
window.addEventListener('load', function() {
    document.querySelectorAll('.station-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        cardObserver.observe(card);
    });
    
    // 간단한 로딩 완료 메시지
    showSimpleMessage('⚡ 충전소 목록 로드 완료!', 'success');
});

function initializeStationSelector() {
    // 키보드 단축키 설정
    document.addEventListener('keydown', function(e) {
        // 숫자키 1-9로 충전소 선택
        if (e.key >= '1' && e.key <= '9') {
            const index = parseInt(e.key) - 1;
            const cards = document.querySelectorAll('.station-card');
            if (cards[index]) {
                cards[index].click();
            }
        }
        
        // ESC키로 첫 번째 충전소 선택
        if (e.key === 'Escape') {
            const firstCard = document.querySelector('.station-card');
            if (firstCard) {
                firstCard.click();
            }
        }
    });
    
    // 카드 호버 효과 개선
    const stationCards = document.querySelectorAll('.station-card');
    stationCards.forEach((card, index) => {
        // 마우스 진입 시
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-8px) scale(1.02)';
            this.style.zIndex = '10';
        });
        
        // 마우스 이탈 시
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
            this.style.zIndex = '1';
        });
        
        // 클릭 시 애니메이션
        card.addEventListener('click', function(e) {
            // 버튼 클릭이 아닌 경우만 처리
            if (!e.target.closest('.btn')) {
                this.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    this.style.transform = 'scale(1)';
                }, 150);
            }
        });
        
        // 순차적 애니메이션을 위한 지연 설정
        card.style.animationDelay = `${index * 0.1}s`;
    });
    
    // 툴팁 기능 추가
    addTooltips();
    
    // 검색 기능 추가
    addSearchFunctionality();
}

function addTooltips() {
    const stationCards = document.querySelectorAll('.station-card');
    stationCards.forEach(card => {
        const stationName = card.querySelector('.station-name').textContent;
        const stationLocation = card.querySelector('.station-location').textContent;
        
        card.setAttribute('title', `${stationName}\n${stationLocation}\n클릭하여 대시보드로 이동`);
    });
}

function addSearchFunctionality() {
    // 검색 입력 필드 생성
    const header = document.querySelector('.header');
    const searchContainer = document.createElement('div');
    searchContainer.className = 'search-container';
    searchContainer.innerHTML = `
        <input type="text" id="station-search" placeholder="충전소 이름 또는 지역으로 검색..." />
        <div class="search-icon">🔍</div>
    `;
    
    // 검색 스타일 추가
    const searchStyle = document.createElement('style');
    searchStyle.textContent = `
        .search-container {
            position: relative;
            max-width: 400px;
            margin: 20px auto 0;
        }
        
        #station-search {
            width: 100%;
            padding: 12px 40px 12px 15px;
            border: none;
            border-radius: 25px;
            background: rgba(255,255,255,0.2);
            color: white;
            font-size: 1em;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.3);
        }
        
        #station-search::placeholder {
            color: rgba(255,255,255,0.7);
        }
        
        #station-search:focus {
            outline: none;
            background: rgba(255,255,255,0.3);
            border-color: rgba(255,255,255,0.5);
        }
        
        .search-icon {
            position: absolute;
            right: 15px;
            top: 50%;
            transform: translateY(-50%);
            color: rgba(255,255,255,0.7);
        }
        
        .station-card.hidden {
            display: none;
        }
        
        .no-results {
            text-align: center;
            padding: 40px;
            color: #666;
            font-size: 1.2em;
        }
    `;
    document.head.appendChild(searchStyle);
    
    header.appendChild(searchContainer);
    
    // 검색 기능 구현
    const searchInput = document.getElementById('station-search');
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase().trim();
        const stationCards = document.querySelectorAll('.station-card');
        let visibleCount = 0;
        
        stationCards.forEach(card => {
            const stationName = card.querySelector('.station-name').textContent.toLowerCase();
            const stationLocation = card.querySelector('.station-location').textContent.toLowerCase();
            const regionBadge = card.querySelector('.region-badge').textContent.toLowerCase();
            
            const isMatch = stationName.includes(searchTerm) || 
                           stationLocation.includes(searchTerm) || 
                           regionBadge.includes(searchTerm);
            
            if (isMatch || searchTerm === '') {
                card.classList.remove('hidden');
                visibleCount++;
            } else {
                card.classList.add('hidden');
            }
        });
        
        // 검색 결과가 없는 경우 메시지 표시
        const stationsGrid = document.querySelector('.stations-grid');
        let noResultsMsg = document.querySelector('.no-results');
        
        if (visibleCount === 0 && searchTerm !== '') {
            if (!noResultsMsg) {
                noResultsMsg = document.createElement('div');
                noResultsMsg.className = 'no-results';
                noResultsMsg.innerHTML = `
                    <div>🔍 검색 결과가 없습니다</div>
                    <div style="font-size: 0.9em; margin-top: 10px; color: #999;">
                        다른 키워드로 검색해보세요
                    </div>
                `;
                stationsGrid.appendChild(noResultsMsg);
            }
        } else {
            if (noResultsMsg) {
                noResultsMsg.remove();
            }
        }
    });
    
    // 엔터키로 첫 번째 검색 결과 선택
    searchInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            const firstVisibleCard = document.querySelector('.station-card:not(.hidden)');
            if (firstVisibleCard) {
                firstVisibleCard.click();
            }
        }
    });
}

async function loadStationStatistics() {
    try {
        showLoadingIndicator();
        
        // 충전소 목록 API 호출
        const response = await fetch('/api/stations');
        if (!response.ok) {
            throw new Error('충전소 정보를 불러올 수 없습니다');
        }
        
        const data = await response.json();
        updateStationCards(data.stations);
        updateHeaderStats(data);
        
    } catch (error) {
        console.error('충전소 통계 로드 실패:', error);
        showErrorMessage('충전소 정보를 불러오는데 실패했습니다');
    } finally {
        hideLoadingIndicator();
    }
}

function updateStationCards(stations) {
    stations.forEach(station => {
        const card = document.querySelector(`[onclick*="${station.id}"]`);
        if (card && station.current_utilization !== "N/A") {
            // 이용률 정보 추가
            const utilizationBadge = document.createElement('div');
            utilizationBadge.className = 'utilization-badge';
            utilizationBadge.textContent = `이용률 ${station.current_utilization}`;
            
            // 이용률에 따른 색상 설정
            const utilization = parseFloat(station.current_utilization);
            if (utilization > 70) {
                utilizationBadge.style.background = '#4caf50';
            } else if (utilization > 40) {
                utilizationBadge.style.background = '#ff9800';
            } else {
                utilizationBadge.style.background = '#f44336';
            }
            
            card.appendChild(utilizationBadge);
        }
    });
    
    // 이용률 배지 스타일 추가
    const utilizationStyle = document.createElement('style');
    utilizationStyle.textContent = `
        .utilization-badge {
            position: absolute;
            bottom: 15px;
            left: 15px;
            color: white;
            padding: 4px 8px;
            border-radius: 10px;
            font-size: 0.75em;
            font-weight: 500;
        }
    `;
    document.head.appendChild(utilizationStyle);
}

function updateHeaderStats(data) {
    const headerP = document.querySelector('.header p');
    if (headerP) {
        headerP.innerHTML = `
            분석할 100kW 급속충전소를 선택하세요 
            (${data.total_stations}개 충전소, ${data.online_stations}개 온라인)
        `;
    }
}

function showLoadingIndicator() {
    const header = document.querySelector('.header');
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'loading-indicator';
    loadingDiv.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: center; margin-top: 15px;">
            <div class="loading-spinner"></div>
            <span style="margin-left: 10px; color: rgba(255,255,255,0.8);">충전소 정보 로딩 중...</span>
        </div>
    `;
    
    const loadingStyle = document.createElement('style');
    loadingStyle.textContent = `
        .loading-spinner {
            width: 20px;
            height: 20px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top: 2px solid white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
    `;
    document.head.appendChild(loadingStyle);
    
    header.appendChild(loadingDiv);
}

function hideLoadingIndicator() {
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.remove();
    }
}

function showErrorMessage(message) {
    const stationsGrid = document.querySelector('.stations-grid');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `
        <div style="text-align: center; padding: 40px; color: #f44336;">
            <div style="font-size: 2em; margin-bottom: 10px;">⚠️</div>
            <div style="font-size: 1.2em; margin-bottom: 10px;">${message}</div>
            <button onclick="location.reload()" style="
                background: #2196f3; 
                color: white; 
                border: none; 
                padding: 10px 20px; 
                border-radius: 5px; 
                cursor: pointer;
                font-size: 1em;
            ">다시 시도</button>
        </div>
    `;
    stationsGrid.appendChild(errorDiv);
}

// 페이지 가시성 API를 사용한 자동 새로고침
document.addEventListener('visibilitychange', function() {
    if (!document.hidden) {
        // 페이지가 다시 보일 때 충전소 정보 새로고침
        setTimeout(() => {
            loadStationStatistics();
        }, 1000);
    }
});

// 브라우저 뒤로가기/앞으로가기 처리
window.addEventListener('popstate', function() {
    // 필요시 상태 복원
    const searchInput = document.getElementById('station-search');
    if (searchInput) {
        searchInput.value = '';
        searchInput.dispatchEvent(new Event('input'));
    }
});

// 터치 디바이스 지원
if ('ontouchstart' in window) {
    document.querySelectorAll('.station-card').forEach(card => {
        card.addEventListener('touchstart', function() {
            this.style.transform = 'translateY(-4px) scale(1.01)';
        });
        
        card.addEventListener('touchend', function() {
            setTimeout(() => {
                this.style.transform = 'translateY(0) scale(1)';
            }, 150);
        });
    });
}

// 접근성 향상
document.addEventListener('keydown', function(e) {
    // Tab 키 네비게이션 개선
    if (e.key === 'Tab') {
        const focusableElements = document.querySelectorAll(
            '.station-card, .btn, input, a[href]'
        );
        const currentIndex = Array.from(focusableElements).indexOf(document.activeElement);
        
        if (e.shiftKey) {
            // Shift + Tab (이전 요소)
            if (currentIndex > 0) {
                e.preventDefault();
                focusableElements[currentIndex - 1].focus();
            }
        } else {
            // Tab (다음 요소)
            if (currentIndex < focusableElements.length - 1) {
                e.preventDefault();
                focusableElements[currentIndex + 1].focus();
            }
        }
    }
});

// 페이지 로드 완료 후 관찰 시작
window.addEventListener('load', function() {
    document.querySelectorAll('.station-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        cardObserver.observe(card);
    });
});