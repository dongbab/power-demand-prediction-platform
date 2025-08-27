<script>
	import { onMount, onDestroy } from 'svelte';
	import { Chart, registerables } from 'chart.js';
	
	Chart.register(...registerables);
	
	export let data = [];
	
	let canvas;
	let chart;
	
	onMount(() => {
		initChart();
	});
	
	onDestroy(() => {
		if (chart) {
			chart.destroy();
		}
	});
	
	$: if (chart && data) {
		updateChart();
	}
	
	function initChart() {
		const ctx = canvas.getContext('2d');
		
		chart = new Chart(ctx, {
			type: 'bar',
			data: {
				labels: [
					'1월', '2월', '3월', '4월', '5월', '6월',
					'7월', '8월', '9월', '10월', '11월', '12월'
				],
				datasets: [{
					label: '예상 최고전력 (kW)',
					data: data || new Array(12).fill(0),
					backgroundColor: 'rgba(78, 205, 196, 0.8)',
					borderColor: '#4ecdc4',
					borderWidth: 2,
					borderRadius: 8,
					borderSkipped: false,
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: {
						display: false
					},
					tooltip: {
						backgroundColor: 'rgba(0,0,0,0.8)',
						titleColor: '#fff',
						bodyColor: '#fff',
						borderColor: '#4ecdc4',
						borderWidth: 1,
						callbacks: {
							label: function(context) {
								return `${context.label}: ${context.parsed.y.toFixed(1)}kW`;
							}
						}
					}
				},
				scales: {
					y: {
						beginAtZero: true,
						max: 100,
						title: {
							display: true,
							text: '전력 (kW)',
							color: '#666',
							font: { size: 12, weight: 'bold' }
						},
						grid: {
							color: 'rgba(0,0,0,0.1)',
							drawBorder: false,
						},
						ticks: {
							color: '#666',
							callback: function(value) {
								return value + 'kW';
							}
						}
					},
					x: {
						grid: { display: false },
						ticks: { color: '#666' }
					}
				},
				animation: {
					duration: 1000,
					easing: 'easeOutQuart'
				}
			}
		});
	}
	
	function updateChart() {
		if (!chart) return;
		
		const chartData = Array.isArray(data) && data.length === 12 ? 
			data.map(val => Number(val) || 0) : 
			new Array(12).fill(0);
			
		chart.data.datasets[0].data = chartData;
		chart.update('active');
	}
</script>

<div class="chart-container">
	<canvas bind:this={canvas}></canvas>
</div>

<style>
	.chart-container {
		position: relative;
		height: 300px;
		margin-top: 20px;
	}
</style>