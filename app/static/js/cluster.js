function initHostChart() {
  const el = document.getElementById('hostChart');
  if (!el) return;
  const c = echarts.init(el);
  const hosts = window.hostData || [];
  c.setOption({
    color: ['#2563eb', '#93c5fd', '#16a34a', '#86efac'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 0 },
    grid: { left: 70, right: 30, top: 35, bottom: 85 },
    xAxis: { type: 'category', data: hosts.map(x => x.name), axisLabel: { rotate: 25 } },
    yAxis: { type: 'value' },
    series: [
      { name: 'CPU已用(核)', type: 'bar', stack: 'cpu', data: hosts.map(x => x.cpu_used_cores) },
      { name: 'CPU剩余(核)', type: 'bar', stack: 'cpu', data: hosts.map(x => Math.max(x.cpu_total_cores - x.cpu_used_cores, 0)) },
      { name: '内存已用(GB)', type: 'bar', stack: 'mem', data: hosts.map(x => x.memory_used_gb) },
      { name: '内存剩余(GB)', type: 'bar', stack: 'mem', data: hosts.map(x => Math.max(x.memory_total_gb - x.memory_used_gb, 0)) }
    ]
  });
  window.addEventListener('resize', () => c.resize());
}
initHostChart();
