<script>
	import { onMount } from 'svelte';
	
	export let title;
	export let value;
	export let unit = '';
	export let type = 'default';
	export let subtitle = '';
	
	let displayValue = 0;
	let element;
	
	onMount(() => {
		animateValue();
	});
	
	$: if (value !== undefined) {
		animateValue();
	}
	
	function animateValue() {
		if (!element) return;
		
		const targetValue = Number(value) || 0;
		const startValue = displayValue;
		const duration = 1000;
		const startTime = performance.now();
		
		function animate(currentTime) {
			const elapsed = currentTime - startTime;
			const progress = Math.min(elapsed / duration, 1);
			
			// easeOutCubic
			const easeProgress = 1 - Math.pow(1 - progress, 3);
			displayValue = startValue + (targetValue - startValue) * easeProgress;
			
			if (progress < 1) {
				requestAnimationFrame(animate);
			} else {
				displayValue = targetValue;
			}
		}
		
		requestAnimationFrame(animate);
	}
</script>

<div class="metric-card {type}" bind:this={element}>
	<h3>{title}</h3>
	<div class="metric-value {type}">
		{displayValue.toFixed(type === 'sessions' ? 0 : 1)}
	</div>
	<div class="metric-unit">{unit}</div>
	{#if subtitle}
		<div class="metric-subtitle">{subtitle}</div>
	{/if}
</div>

<style>
	.metric-card {
		background: var(--bg-secondary, white);
		border: 1px solid var(--border-color, rgba(0, 0, 0, 0.1));
		border-radius: 12px;
		padding: 24px;
		box-shadow: 0 4px 6px var(--shadow, rgba(0, 0, 0, 0.05));
		text-align: center;
		transition: all 0.3s ease;
		color: var(--text-primary, #333);
	}
	
	/* 알고리즘 예측 카드 특별 스타일 */
	.metric-card.algorithm {
		border-color: var(--metric-algorithm, #8b5cf6);
		background: linear-gradient(135deg, var(--bg-secondary, white) 0%, rgba(139, 92, 246, 0.05) 100%);
	}
	
	.metric-card:hover {
		transform: translateY(-4px);
		box-shadow: 0 8px 25px var(--shadow-hover, rgba(0, 0, 0, 0.15));
		border-color: var(--primary-color, #4f46e5);
	}
	
	.metric-card h3 {
		margin: 0 0 15px 0;
		color: var(--text-secondary, #666);
		font-size: 1em;
		font-weight: 600;
	}
	
	.metric-value {
		font-size: 2.5em;
		font-weight: bold;
		margin: 10px 0;
		line-height: 1;
		transition: color 0.3s ease;
	}
	
	/* 타입별 색상 - 다크모드 호환 */
	.metric-value.power { 
		color: var(--metric-power, #ff6b6b); 
	}
	.metric-value.contract { 
		color: var(--metric-contract, #4ecdc4); 
	}
	.metric-value.utilization { 
		color: var(--metric-utilization, #45b7d1); 
	}
	.metric-value.sessions { 
		color: var(--metric-sessions, #96ceb4); 
	}
	.metric-value.confidence { 
		color: var(--metric-confidence, #f59e0b); 
	}
	.metric-value.algorithm { 
		color: var(--metric-algorithm, #8b5cf6); 
	}
	.metric-value.energy { 
		color: var(--metric-energy, #10b981); 
	}
	.metric-value.total { 
		color: var(--metric-total, #3b82f6); 
	}
	.metric-value.growth { 
		color: var(--metric-growth, #f59e0b); 
	}
	.metric-value.peak { 
		color: var(--metric-peak, #ef4444); 
	}
	.metric-value.default { 
		color: var(--metric-default, #667eea); 
	}
	
	.metric-unit {
		color: var(--text-tertiary, #999);
		font-size: 1em;
		font-weight: 500;
		margin: 0;
		transition: color 0.3s ease;
	}
	
	.metric-subtitle {
		color: var(--text-tertiary, #999);
		font-size: 0.75em;
		font-weight: 400;
		margin-top: 8px;
		padding: 4px 8px;
		background: var(--bg-tertiary, rgba(0, 0, 0, 0.05));
		border-radius: 12px;
		display: inline-block;
	}

	/* 다크모드 전용 스타일 */
	:global([data-theme="dark"]) .metric-card {
		--bg-secondary: #1f2937;
		--bg-tertiary: rgba(255, 255, 255, 0.05);
		--border-color: #374151;
		--shadow: rgba(0, 0, 0, 0.3);
		--shadow-hover: rgba(0, 0, 0, 0.5);
		--text-primary: #f9fafb;
		--text-secondary: #d1d5db;
		--text-tertiary: #9ca3af;
		--primary-color: #6366f1;
		
		/* 다크모드에서 더 밝은 색상으로 조정 */
		--metric-power: #fca5a5;
		--metric-contract: #67e8f9;
		--metric-utilization: #7dd3fc;
		--metric-sessions: #86efac;
		--metric-confidence: #fbbf24;
		--metric-algorithm: #c084fc;
		--metric-energy: #86efac;
		--metric-total: #7dd3fc;
		--metric-growth: #fbbf24;
		--metric-peak: #fca5a5;
		--metric-default: #a78bfa;
	}

	/* 라이트모드 전용 스타일 */
	:global([data-theme="light"]) .metric-card {
		--bg-secondary: #ffffff;
		--bg-tertiary: rgba(0, 0, 0, 0.05);
		--border-color: rgba(0, 0, 0, 0.1);
		--shadow: rgba(0, 0, 0, 0.05);
		--shadow-hover: rgba(0, 0, 0, 0.15);
		--text-primary: #111827;
		--text-secondary: #6b7280;
		--text-tertiary: #9ca3af;
		--primary-color: #4f46e5;
		
		/* 라이트모드 원래 색상 */
		--metric-power: #ef4444;
		--metric-contract: #06b6d4;
		--metric-utilization: #3b82f6;
		--metric-sessions: #10b981;
		--metric-confidence: #f59e0b;
		--metric-algorithm: #8b5cf6;
		--metric-energy: #10b981;
		--metric-total: #3b82f6;
		--metric-growth: #f59e0b;
		--metric-peak: #ef4444;
		--metric-default: #6366f1;
	}
</style>