<script>
	import { onMount, afterUpdate, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { stations, isLoading, isLoadingMore, error, stationActions, pagination, requiresUpload, hasData } from '../stores/stationStore.ts';
	import { uiActions } from '../stores/uiStore.ts';
	import { searchQuery, sortBy, sortOrder, filteredStations, searchActions } from '../stores/searchStore.ts';
	import LoadingSpinner from '../components/LoadingSpinner.svelte';
	import ThemeToggle from '../components/ThemeToggle.svelte';
	import FileUpload from '../lib/components/FileUpload.svelte';
	import { tweened } from 'svelte/motion';
	import { cubicOut } from 'svelte/easing';

	let scrollContainer;
	
	// Debounce timer for search (클라이언트 사이드 검색이므로 더 짧은 디바운스)
	let searchTimeout;
	
	// Scroll cleanup function
	let scrollCleanup;
	
	onMount(async () => {
		await stationActions.checkSystemStatus();
		await stationActions.loadStations();
		scrollCleanup = setupInfiniteScroll();
	});
	
	function setupInfiniteScroll() {
		const handleScroll = () => {
			// 메인 네비게이션 스크롤 사용
			const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
			const nearBottom = scrollTop + clientHeight >= scrollHeight - 300; // 300px 여유
			
			if (nearBottom && !$isLoadingMore && $pagination.hasNext) {
				stationActions.loadMore();
			}
		};

		// 전체 페이지 스크롤에 이벤트 리스너 추가
		window.addEventListener('scroll', handleScroll, { passive: true });
		return () => window.removeEventListener('scroll', handleScroll);
	}
	
	onDestroy(() => {
		if (scrollCleanup) {
			scrollCleanup();
		}
	});
	
	function selectStation(station) {
		stationActions.setCurrentStation(station);
		goto(`/dashboard/${station.id}`);
	}
	
	function refreshStations() {
		stationActions.loadStations();
		uiActions.showNotification('로드 중...', 'info');
	}
	
	// 클라이언트 사이드 검색 핸들러
	function handleSearch(query) {
		searchActions.updateSearch(query);
	}
	
	// 더 빠른 디바운스 (클라이언트 사이드이므로 50ms로 단축)
	function debouncedSearch(query) {
		if (searchTimeout) {
			clearTimeout(searchTimeout);
		}
		searchTimeout = setTimeout(() => {
			handleSearch(query);
		}, 50); // 50ms delay
	}
	
	function handleSortChange(field, order) {
		searchActions.updateSort(field, order);
	}
	
	function clearSearch() {
		$searchQuery = '';
		searchActions.clearSearch();
	}
	
	// Reactive statements (클라이언트 사이드 검색으로 즉시 반응)
	$: if (browser && $searchQuery !== undefined) {
		debouncedSearch($searchQuery);
	}
	
	$: if (browser && ($sortBy || $sortOrder)) {
		handleSortChange($sortBy, $sortOrder);
	}


	const stationCount = tweened(0, { duration: 500, easing: cubicOut });

	// 총 세션 수 집계 (필터링된 결과 기준)
	$: totalSessions = ($filteredStations || []).reduce((sum, s) => sum + (s?.data_sessions || 0), 0);

	// 필터링된 스테이션 수가 바뀔 때 애니메이션
	$: stationCount.set(($filteredStations || []).length);
</script>

<svelte:head>
	<title>블루네트웍스 전력 예측 시스템</title>
</svelte:head>

<div class="container">
	<div class="header">
		<div class="header-content">
			<div class="header-text">
				<h1>블루네트웍스 충전소 전력 예측 시스템</h1>
			</div>
			<div class="header-actions">
				<ThemeToggle />
			</div>
		</div>
	</div>

	{#if $error}
		<div class="alert alert-error">
			<strong>오류</strong> {$error}
			<button class="btn" on:click={() => stationActions.clearError()}>
				닫기
			</button>
		</div>
	{/if}

	<!-- 업로드가 필요한 경우 -->
	{#if $requiresUpload}
		<div class="upload-required-container">
			<FileUpload on:uploaded={() => {
				stationActions.loadStations();
			}} />
		</div>
	{:else}
		<!-- 선택적 추가 업로드 -->
		<div class="additional-upload">
			<FileUpload on:uploaded={() => {
				stationActions.loadStations();
			}} />
		</div>
	
	<div class="dashboard-overview">
        <div class="overview-header">
            <h1 class="section-title">충전소 개요</h1>
            <button class="refresh-btn" on:click={refreshStations} disabled={$isLoading}>
                {#if $isLoading}
                    <LoadingSpinner size="small" />
                {:else}
                    <svg class="refresh-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path d="M23 4v6h-6"/>
                        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                    </svg>
                {/if}
                <span>새로고침</span>
            </button>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card featured">
                <div class="stat-header">
                    <div class="stat-icon-wrapper primary">
                        <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                        </svg>
                    </div>
                    <div class="stat-badge">실시간</div>
                </div>
                <div class="stat-content">
                    <div class="stat-value">{$stationCount}</div>
                    <div class="stat-label">총 충전소</div>
                </div>
                <div class="stat-footer">
                    <div class="stat-trend positive">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
                            <polyline points="17 6 23 6 23 12"/>
                        </svg>
                        <span>활성</span>
                    </div>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-header">
                    <div class="stat-icon-wrapper secondary">
                        <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                            <line x1="9" y1="9" x2="9" y2="15"/>
                            <line x1="15" y1="9" x2="15" y2="15"/>
                        </svg>
                    </div>
                    <div class="stat-metric">세션</div>
                </div>
                <div class="stat-content">
                    <div class="stat-value">{(totalSessions || 0).toLocaleString()}</div>
                    <div class="stat-label">총 충전 세션</div>
                </div>
                <div class="stat-footer">
                    <div class="stat-detail">
                        <span>누적 데이터</span>
                    </div>
                </div>
            </div>

            <div class="stat-card">
                <div class="stat-header">
                    <div class="stat-icon-wrapper tertiary">
                        <svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                            <circle cx="12" cy="12" r="3"/>
                            <path d="M12 1v6m0 6v6m11-7h-6m-6 0H1"/>
                        </svg>
                    </div>
                    <div class="stat-metric">전체</div>
                </div>
                <div class="stat-content">
                    <div class="stat-value">{($pagination?.total ?? $stations.length)}</div>
                    <div class="stat-label">등록된 개소</div>
                </div>
                <div class="stat-footer">
                    <div class="stat-detail">
                        <span>시스템 등록</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

	<div class="search-section">
		<div class="search-container">
			<div class="search-box">
				<div class="search-icon">🔍</div>
				<input
					type="text"
					class="search-input"
					placeholder="충전소 ID, 이름, 위치로 검색"
					bind:value={$searchQuery}
				/>
				{#if $isLoading}
					<div class="search-loading">
						<LoadingSpinner size="small" />
					</div>
				{/if}
				{#if $searchQuery}
					<button class="clear-button" on:click={clearSearch} title="검색어 지우기">
						✕
					</button>
				{/if}
			</div>
			
			<div class="filter-controls modern">
    <div class="control-group">
        <label class="control-label" for="sort-by-select">정렬 기준</label>
        <div class="select-wrapper">
            <svg class="select-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
                <path d="M8 9l4-4 4 4" />
                <path d="M16 15l-4 4-4-4" />
            </svg>
            <select
                id="sort-by-select"
                class="select"
                bind:value={$sortBy}
                aria-label="정렬 기준 선택"
            >
                <option value="id">ID</option>
                <option value="name">이름</option>
                <option value="location">위치</option>
                <option value="region">권역</option>
                <option value="city">시군구</option>
                <option value="sessions">세션수</option>
                <option value="avg_power">평균 전력</option>
                <option value="max_power">최대 전력</option>
                <option value="capacity_efficiency">용량 효율성</option>
                <option value="charger_type">충전기 타입</option>
                <option value="last_activity">마지막 활동</option>
            </select>
        </div>
    </div>

    <div class="control-group">
        <div class="sort-control segmented">
            <span class="control-label">정렬</span>
            <div class="sort-toggle-switch" role="group" aria-label="정렬 방향">
                <button
                    type="button"
                    class="toggle-option"
                    class:active={$sortOrder === 'asc'}
                    aria-pressed={$sortOrder === 'asc'}
                    on:click={() => ($sortOrder = 'asc')}
                    title="오름차순 정렬"
                >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <polygon points="12 6, 6 18, 18 18"></polygon>
                    </svg>
                    <span>오름차순 (A-Z)</span>
                </button>
                <button
                    type="button"
                    class="toggle-option"
                    class:active={$sortOrder === 'desc'}
                    aria-pressed={$sortOrder === 'desc'}
                    on:click={() => ($sortOrder = 'desc')}
                    title="내림차순 정렬"
                >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                        <polygon points="6 6, 18 6, 12 18"></polygon>
                    </svg>
                    <span>내림차순 (Z-A)</span>
                </button>
            </div>
        </div>
    </div>
</div>
		</div>
	</div>

	{#if $isLoading}
		<div class="loading-container">
			<LoadingSpinner size="large" />
			<p>충전소 정보를 로드하는 중...</p>
		</div>
	{:else if $filteredStations.length === 0}
		<div class="empty-state">
			<h3>📂 충전소 데이터가 없습니다</h3>
			<p>파일을 업로드하거나 서버 연결을 확인해보세요.</p>
			<div class="empty-actions">
				<button class="btn" on:click={refreshStations}>
					🔄 다시 시도
				</button>
			</div>
		</div>
	{:else}
		<div class="station-grid" bind:this={scrollContainer}>
			{#each $filteredStations as station (station.id)}
				<div class="station-card">
						<div class="station-identity">
							<h3 class="station-name" title="{station.name}">{station.name}</h3>
							<div class="station-id">{station.id}</div>
							<div class="station-location" title="{station.location}">
								<svg class="location-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
									<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
									<circle cx="12" cy="10" r="3"/>
								</svg>
								<div class="location-info">
									{#if station.region || station.city}
										<span class="location-region">{station.region} {station.city}</span>
									{/if}
									<span class="location-address">{station.location}</span>
								</div>
							</div>
						</div>
						
						<div class="station-specs">
							<div class="spec-item">
								<svg class="spec-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
									<path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
								</svg>
								<span>{station.charger_type}</span>
							</div>
							<div class="spec-item">
								<svg class="spec-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
									<circle cx="12" cy="12" r="3"/>
									<path d="M12 1v6m0 6v6m11-7h-6m-6 0H1"/>
								</svg>
								<span>{station.connector_type}</span>
							</div>
						</div>
						
						<div class="station-metrics">
							<div class="metric-grid">
								<div class="metric-item primary">
									<div class="metric-value">{station.data_sessions || 0}</div>
									<div class="metric-label">충전 세션</div>
								</div>
								<div class="metric-item secondary">
									<div class="metric-value capacity-efficiency" title="평균 사용량 / 정격 용량 × 100%">{station.capacity_efficiency || 'N/A'}</div>
									<div class="metric-label">
										용량 효율성
									</div>
								</div>
							</div>
						</div>
						
						{#if station.last_activity}
							<div class="station-activity">
								<svg class="activity-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
									<circle cx="12" cy="12" r="10"/>
									<polyline points="12,6 12,12 16,14"/>
								</svg>
								<span class="activity-text">마지막 활동: {station.last_activity}</span>
							</div>
						{/if}
						
						<div class="card-footer" on:click={() => selectStation(station)} role="button" tabindex="0" on:keydown={(e) => e.key === 'Enter' && selectStation(station)}>
							<div class="view-details">
								<span>상세 정보 보기</span>
								<svg class="arrow-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
									<path d="M9 18l6-6-6-6"/>
								</svg>
							</div>
						</div>
					</div>
			{/each}
			
			{#if $isLoadingMore}
				<div class="loading-more">
					<LoadingSpinner />
					<p>더 많은 충전소를 불러오는 중...</p>
				</div>
			{:else if !$pagination.hasNext && $filteredStations.length > 0}
				<div class="end-message">
					{#if $searchQuery}
						<p>검색 결과: {$filteredStations.length}개소 (전체 {$pagination.total}개소 중)</p>
					{:else}
						<p>총 {$pagination.total}개소의 충전소가 로드되었습니다.</p>
					{/if}
				</div>
			{/if}
		</div>
		{/if}
	{/if}
</div>

<style>
	.header {
		margin-bottom: 40px;
		padding: 40px 20px;
		background: var(--gradient-primary);
		color: white;
		border-radius: 16px;
		box-shadow: 0 8px 32px var(--shadow);
	}
	
	.header-content {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
		gap: 20px;
	}
	
	.header-text {
		text-align: left;
	}
	
	.header h1 {
		margin: 0 0 10px 0;
		font-size: 2.5em;
		font-weight: 700;
	}
	
	.header p {
		margin: 0;
		font-size: 1.2em;
		opacity: 0.9;
	}
	
	.header-actions {
		display: flex;
		gap: 12px;
	}

	.upload-required-container {
		margin-bottom: 2rem;
	}

	.additional-upload {
		margin-bottom: 2rem;
		padding: 1rem;
		background: var(--bg-secondary);
		border-radius: 12px;
		border: 1px solid var(--border-color);
	}
	
	
	.dashboard-overview {
		background: linear-gradient(135deg, var(--neutral-light) 0%, var(--bg-secondary) 100%);
		border-radius: 24px;
		padding: 32px;
		margin-bottom: 40px;
		border: 1px solid var(--border-color);
		box-shadow: 0 10px 40px var(--shadow);
		transition: background 0.3s ease, border-color 0.3s ease;
	}
	
	.overview-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 28px;
		flex-wrap: wrap;
		gap: 20px;
	}
	
	.section-title {
		margin: 0;
		font-size: 1.5em;
		font-weight: 700;
		color: var(--primary-color);
		display: flex;
		align-items: center;
		gap: 12px;
	}
	
	.refresh-btn {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 12px 20px;
		background: var(--gradient-primary);
		color: white;
		border: none;
		border-radius: 14px;
		font-weight: 600;
		font-size: 0.95em;
		cursor: pointer;
		transition: all 0.3s ease;
		box-shadow: 0 4px 15px var(--shadow);
	}
	
	.refresh-btn:hover:not(:disabled) {
		transform: translateY(-2px);
		box-shadow: 0 8px 25px var(--shadow-hover);
	}
	
	.refresh-btn:disabled {
		background: var(--text-muted);
		cursor: not-allowed;
		transform: none;
		box-shadow: 0 2px 8px var(--shadow);
	}
	
	.refresh-icon {
		width: 18px;
		height: 18px;
		stroke-width: 2;
	}
	
	.stats-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
		gap: 24px;
	}
	
	.stat-card {
		background: var(--bg-secondary);
		border-radius: 20px;
		padding: 28px;
		border: 1px solid var(--border-color);
		transition: all 0.3s ease;
		position: relative;
		overflow: hidden;
	}
	
	.stat-card::before {
		content: '';
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 4px;
		background: var(--gradient-primary);
		opacity: 0;
		transition: opacity 0.3s ease;
	}
	
	.stat-card:hover {
		transform: translateY(-4px);
		box-shadow: 0 15px 35px var(--shadow-hover);
		border-color: var(--primary-color);
	}
	
	.stat-card:hover::before {
		opacity: 1;
	}
	
	.stat-card.featured {
		background: var(--gradient-primary);
		color: white;
		border: none;
		box-shadow: 0 10px 30px rgba(46, 86, 166, 0.3);
	}
	
	.stat-card.featured::before {
		background: rgba(255, 255, 255, 0.2);
	}
	
	.stat-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 20px;
	}
	
	.stat-icon-wrapper {
		width: 48px;
		height: 48px;
		border-radius: 14px;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.3s ease;
	}
	
	.stat-icon-wrapper.primary {
		background: rgba(255, 255, 255, 0.2);
	}
	
	.stat-icon-wrapper.secondary {
		background: linear-gradient(135deg, var(--primary-light) 0%, var(--primary-color) 100%);
		color: white;
	}
	
	.stat-icon-wrapper.tertiary {
		background: linear-gradient(135deg, var(--primary-medium) 0%, var(--primary-soft) 100%);
		color: white;
	}
	
	.stat-icon {
		width: 24px;
		height: 24px;
		stroke-width: 2;
	}
	
	.stat-badge {
		background: rgba(255, 255, 255, 0.2);
		padding: 6px 12px;
		border-radius: 20px;
		font-size: 0.75em;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}
	
	.stat-metric {
		background: var(--neutral-light);
		padding: 6px 12px;
		border-radius: 20px;
		font-size: 0.75em;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		color: var(--text-muted);
		transition: background-color 0.3s ease, color 0.3s ease;
	}
	
	.stat-content {
		margin-bottom: 20px;
	}
	
	.stat-value {
		font-size: 2.5em;
		font-weight: 800;
		line-height: 1;
		margin-bottom: 8px;
		letter-spacing: -0.025em;
	}
	
	.stat-card.featured .stat-value {
		color: white;
	}
	
	.stat-label {
		font-size: 0.95em;
		font-weight: 500;
		color: var(--text-muted);
		text-transform: capitalize;
	}
	
	.stat-card.featured .stat-label {
		color: rgba(255, 255, 255, 0.9);
	}
	
	.stat-footer {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	
	.stat-trend {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 0.85em;
		font-weight: 500;
	}
	
	.stat-trend svg {
		width: 16px;
		height: 16px;
		stroke-width: 2;
	}
	
	.stat-trend.positive {
		color: rgba(255, 255, 255, 0.9);
	}
	
	.stat-detail {
		font-size: 0.85em;
		color: var(--text-muted);
		font-weight: 500;
	}
	
	/* Sort Control Styles */
	.sort-control {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.sort-toggle-switch {
		display: flex;
		background: var(--neutral-light);
		border-radius: 8px;
		padding: 2px;
		border: 1px solid var(--border-color);
		transition: all 0.3s ease;
	}

	.toggle-option {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 12px;
		border: none;
		background: transparent;
		border-radius: 6px;
		cursor: pointer;
		font-size: 1rem; /* 기존 0.85em -> 1rem */
		font-weight: 600;
		color: var(--text-secondary);
		transition: all 0.2s ease;
		min-width: 60px;
		justify-content: center;
	}

	.toggle-option span {
		font-weight: 700;
		font-size: 0.95rem; /* 기존 0.8em -> 0.95rem */
		letter-spacing: 0.2px;
	}

	/* Modern filter controls (세그먼티드 내부 버튼) */
	.sort-control.segmented .sort-toggle-switch {
		display: inline-flex;
		background: var(--neutral-light);
		border-radius: 12px;
		padding: 4px;
		border: 1px solid var(--border-color);
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 4px 14px var(--shadow);
		gap: 4px;
	}

	.sort-toggle-switch .toggle-option {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 14px;
		border: none;
		background: transparent;
		border-radius: 10px;
		cursor: pointer;
		font-size: 1rem; /* 기존 0.85rem -> 1rem */
		font-weight: 700;
		color: var(--text-secondary);
		min-width: 92px;
		justify-content: center;
		transition: background 0.2s ease, color 0.2s ease, transform 0.08s ease;
	}

	.toggle-option:hover {
		background: rgba(var(--primary-rgb), 0.1);
		color: var(--primary-color);
	}

	.toggle-option.active {
		background: var(--primary-color);
		color: white;
		box-shadow: 0 2px 4px rgba(var(--primary-rgb), 0.3);
		transform: translateY(-1px);
	}

	.toggle-option svg {
		transition: all 0.2s ease;
	}

	.toggle-option.active svg {
		stroke-width: 2.5;
	}

	.toggle-option span {
		font-weight: 600;
		font-size: 0.8em;
		letter-spacing: 0.5px;
	}

	/* Loading and scrollbar components moved to layout.svelte */
	
	/* Loading more and end message moved to layout.svelte */
	
	.station-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
		gap: 20px;
		padding: 20px 0;
		margin-bottom: 40px;
	}
	
	/* 로딩 및 종료 메시지 스타일 */
	.loading-more,
	.end-message {
		grid-column: 1 / -1;
		text-align: center;
		padding: 40px 20px;
		margin-top: 20px;
	}
	
	.loading-more {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 16px;
		color: var(--text-muted);
	}
	
	.end-message {
		background: var(--neutral-light);
		border-radius: 12px;
		border: 1px solid var(--border-color);
		color: var(--text-secondary);
		font-weight: 500;
	}
	
	.station-card {
		background: var(--bg-secondary);
		border-radius: 20px;
		padding: 0;
		box-shadow: 0 4px 20px var(--shadow);
		transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
		border: 1px solid var(--border-color);
		display: flex;
		flex-direction: column;
		overflow: hidden;
		position: relative;
	}
	
	.station-card::before {
		content: '';
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 4px;
		background: var(--gradient-primary);
		transform: scaleX(0);
		transition: transform 0.3s ease;
	}
	
	
	
	.station-identity {
		padding: 24px 24px 0 24px;
		margin-bottom: 20px;
	}
	
	.station-name {
		margin: 0 0 6px 0;
		font-size: 1.4em;
		font-weight: 700;
		color: var(--primary-color);
		line-height: 1.3;
		height: 2.6em; /* 2줄 고정 높이 */
		overflow: hidden;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
	}
	
	.station-id {
		margin: 0 0 12px 0;
		font-size: 0.85em;
		font-weight: 600;
		color: var(--text-muted);
		background: var(--neutral-light);
		padding: 4px 8px;
		border-radius: 6px;
		display: inline-block;
		letter-spacing: 0.5px;
		font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
	}
	
	.station-location {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		color: var(--text-secondary);
		font-size: 0.9em;
		line-height: 1.3;
	}
	
	.location-icon {
		width: 16px;
		height: 16px;
		stroke-width: 2;
		color: #ef4444;
		flex-shrink: 0;
		margin-top: 2px;
	}
	
	.location-info {
		flex: 1;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	
	.location-region {
		font-weight: 600;
		color: var(--primary-color);
		font-size: 0.85em;
		opacity: 0.8;
	}
	
	.location-address {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 0.85em;
		color: var(--text-muted);
	}
	
	.station-specs {
		padding: 0 24px;
		margin-bottom: 20px;
	}
	
	.spec-item {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 8px 0;
		font-size: 0.9em;
		color: var(--text-secondary);
	}
	
	.spec-icon {
		width: 18px;
		height: 18px;
		stroke-width: 2;
		color: var(--primary-color);
	}
	
	.station-metrics {
		padding: 0 24px;
		margin-bottom: 20px;
	}
	
	.metric-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	
	.metric-item {
		background: var(--neutral-light);
		border-radius: 12px;
		padding: 16px;
		text-align: center;
		transition: all 0.3s ease;
		border: 2px solid transparent;
	}
	
	.metric-item.primary {
		background: var(--gradient-primary);
		color: white;
	}
	
	.metric-item.secondary {
		background: linear-gradient(135deg, var(--neutral-light) 0%, var(--bg-tertiary) 100%);
		color: var(--text-primary);
	}
	
	.metric-item:hover {
		transform: translateY(-2px);
		border-color: var(--border-color);
	}
	
	.metric-value {
		font-size: 1.5em;
		font-weight: 700;
		line-height: 1;
		margin-bottom: 4px;
	}
	
	.metric-item.primary .metric-value {
		color: white;
	}
	
	.metric-item.secondary .metric-value {
		color: var(--primary-color);
	}
	
	.metric-label {
		font-size: 0.8em;
		font-weight: 500;
		opacity: 0.8;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}
	
	.metric-item.primary .metric-label {
		color: rgba(255, 255, 255, 0.9);
	}
	
	.metric-item.secondary .metric-label {
		color: var(--text-secondary);
	}
	
	.station-activity {
		padding: 0 24px;
		margin-bottom: 20px;
		display: flex;
		align-items: center;
		gap: 8px;
		color: var(--text-muted);
		font-size: 0.85em;
	}
	
	.activity-icon {
		width: 14px;
		height: 14px;
		stroke-width: 2;
	}
	
	.card-footer {
		padding: 20px 24px 24px 24px;
		margin-top: auto;
		border-top: 1px solid var(--border-color);
		background: var(--neutral-light);
		transition: all 0.3s ease;
		cursor: pointer;
		outline: none;
	}
	
	.card-footer:hover {
		background: var(--primary-color);
		border-top-color: var(--primary-color);
		transform: translateY(-2px);
	}
	
	.card-footer:active {
		transform: translateY(0);
	}
	
	.view-details {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		font-size: 1.1em;
		font-weight: 600;
		color: var(--primary-color);
		transition: all 0.3s ease;
	}
	
	.card-footer:hover .view-details {
		color: white;
		transform: translateX(4px);
	}
	
	.arrow-icon {
		width: 16px;
		height: 16px;
		stroke-width: 2;
		transition: transform 0.3s ease;
	}
	
	.card-footer:hover .arrow-icon {
		transform: translateX(4px);
	}
	
	.btn-primary {
		background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
		width: 100%;
		padding: 12px 20px;
		font-weight: 600;
	}
	
	.btn-primary:disabled {
		background: #ccc;
		cursor: not-allowed;
	}
	
	/* 툴팁 스타일 */
	.calculation-info {
		position: relative;
		display: inline-block;
		margin-left: 4px;
	}
	
	.info-icon {
		width: 14px;
		height: 14px;
		color: var(--text-muted);
		cursor: help;
		transition: color 0.2s ease;
	}
	
	.info-icon:hover {
		color: var(--primary-color);
	}
	
	.tooltip {
		position: absolute;
		bottom: 100%;
		left: 50%;
		transform: translateX(-50%);
		background: var(--bg-primary);
		border: 1px solid var(--border-color);
		border-radius: 8px;
		padding: 12px 16px;
		font-size: 12px;
		white-space: nowrap;
		box-shadow: 0 4px 20px var(--shadow);
		opacity: 0;
		visibility: hidden;
		transition: all 0.3s ease;
		z-index: 1000;
		max-width: 280px;
		white-space: normal;
	}
	
	.calculation-info:hover .tooltip {
		opacity: 1;
		visibility: visible;
		transform: translateX(-50%) translateY(-8px);
	}
	
	.tooltip-formula {
		margin-bottom: 6px;
		line-height: 1.3;
	}
	
	.capacity-examples {
		font-style: italic;
		color: var(--text-muted);
		font-size: 11px;
		line-height: 1.2;
	}
	
	/* Modern filter controls */
.filter-controls.modern {
    display: flex;
    align-items: flex-end;
    gap: 16px;
    padding: 12px 16px;
    background: linear-gradient(180deg, var(--bg-secondary) 0%, var(--neutral-light) 100%);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    box-shadow: 0 6px 20px var(--shadow);
    backdrop-filter: saturate(140%) blur(6px);
}

.filter-controls.modern .control-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 220px;
}

.select-wrapper {
    position: relative;
    display: flex;
    align-items: center;
}

.select-wrapper .select {
    appearance: none;
    -webkit-appearance: none;
    width: 100%;
    padding: 12px 40px 12px 40px;
    border-radius: 10px;
    border: 1px solid var(--border-color);
    background: var(--bg-secondary);
    color: var(--text-primary);
    font-weight: 600;
    cursor: pointer;
    transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.08s ease;
    box-shadow: 0 2px 8px var(--shadow);
}

.select-wrapper .select:focus {
    outline: none;
    border-color: var(--primary-color);
    box-shadow: 0 0 0 4px rgba(var(--primary-rgb), 0.12);
}

.select-wrapper .select:hover {
    border-color: var(--primary-color);
}

.select-wrapper .select-icon {
    position: absolute;
    left: 12px;
    width: 18px;
    height: 18px;
    stroke-width: 2;
    color: var(--primary-color);
    pointer-events: none;
    opacity: 0.9;
}

.sort-control.segmented .sort-toggle-switch {
    display: inline-flex;
    background: var(--neutral-light);
    border-radius: 12px;
    padding: 4px;
    border: 1px solid var(--border-color);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 4px 14px var(--shadow);
    gap: 4px;
}

.sort-toggle-switch .toggle-option {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border: none;
    background: transparent;
    border-radius: 10px;
    cursor: pointer;
    font-size: 1rem; /* 기존 0.85rem -> 1rem */
    font-weight: 700;
    color: var(--text-secondary);
    min-width: 92px;
    justify-content: center;
    transition: background 0.2s ease, color 0.2s ease, transform 0.08s ease;
}

.sort-toggle-switch .toggle-option:hover {
    background: rgba(var(--primary-rgb), 0.10);
    color: var(--primary-color);
}

.sort-toggle-switch .toggle-option.active {
    background: var(--primary-color);
    color: #fff;
    box-shadow: 0 4px 10px rgba(var(--primary-rgb), 0.35);
    transform: translateY(-1px);
}

.sort-toggle-switch .toggle-option svg {
    transition: transform 0.2s ease;
}

.sort-toggle-switch .toggle-option.active svg {
    transform: translateY(-1px);
}

/* Responsive tweaks */
@media (max-width: 767px) {
    .filter-controls.modern {
        flex-direction: column;
        align-items: stretch;
        gap: 12px;
        padding: 12px;
    }
    .filter-controls.modern .control-group {
        min-width: 0;
    }
}
/* End modern filter controls */

/* ...existing code... */
</style>