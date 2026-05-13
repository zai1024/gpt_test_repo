const palette = ['#2563eb', '#16a34a', '#f59e0b', '#8b5cf6', '#06b6d4', '#ef4444', '#84cc16', '#f97316'];
const percent = (used, total) => total ? `${Math.round((used / total) * 100)}%` : '0%';
const vmLink = (group, value, snapshotId) => `/vms?group=${encodeURIComponent(group)}&value=${encodeURIComponent(value)}&snapshot_id=${snapshotId}`;

function chart(id) {
  return echarts.init(document.getElementById(id));
}

function renderCluster(data) {
  const c = chart('clusterChart');
  const names = data.clusters.map(x => x.name);
  c.setOption({
    color: ['#2563eb', '#93c5fd', '#16a34a', '#86efac'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 0 },
    grid: { left: 60, right: 25, top: 35, bottom: 70 },
    xAxis: { type: 'category', data: names, axisLabel: { rotate: 20 } },
    yAxis: { type: 'value' },
    series: [
      { name: 'CPU已用(核)', type: 'bar', stack: 'cpu', data: data.clusters.map(x => x.cpu_used_cores) },
      { name: 'CPU剩余(核)', type: 'bar', stack: 'cpu', data: data.clusters.map(x => Math.max(x.cpu_total_cores - x.cpu_used_cores, 0)) },
      { name: '内存已用(GB)', type: 'bar', stack: 'mem', data: data.clusters.map(x => x.memory_used_gb) },
      { name: '内存剩余(GB)', type: 'bar', stack: 'mem', data: data.clusters.map(x => Math.max(x.memory_total_gb - x.memory_used_gb, 0)) }
    ]
  });
  c.on('click', p => { if (p.name) location.href = `/clusters/${encodeURIComponent(p.name)}`; });
}

function renderDatastore(data) {
  chart('datastoreChart').setOption({
    color: ['#f59e0b', '#fde68a'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 0 },
    grid: { left: 70, right: 20, top: 25, bottom: 95 },
    xAxis: { type: 'category', data: data.datastores.map(x => x.name), axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: 'TB' },
    series: [
      { name: '已使用', type: 'bar', stack: 'space', data: data.datastores.map(x => x.used_tb) },
      { name: '剩余', type: 'bar', stack: 'space', data: data.datastores.map(x => x.free_tb) }
    ]
  });
}

function renderPie(id, rows, group, snapshotId) {
  const c = chart(id);
  c.setOption({
    color: palette,
    tooltip: { formatter: p => `${p.name}<br/>虚拟机：${p.value} 台<br/>占比：${p.percent}%` },
    legend: { type: 'scroll', orient: 'vertical', right: 0, top: 20, bottom: 20 },
    series: [{
      type: 'pie', radius: ['42%', '72%'], center: ['38%', '52%'],
      label: { formatter: '{b}\n{c}台' },
      data: rows.map(x => ({ name: x.name, value: x.vm_count, raw: x }))
    }]
  });
  c.on('click', p => { location.href = vmLink(group, p.name, snapshotId); });
}

function renderTrend(id, rows, group, snapshotId) {
  const c = chart(id);
  c.setOption({
    color: ['#2563eb', '#16a34a', '#f59e0b'],
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0 },
    grid: { left: 55, right: 35, top: 35, bottom: 65 },
    xAxis: { type: 'category', data: rows.map(x => x.name) },
    yAxis: [{ type: 'value', name: '台/核' }, { type: 'value', name: 'GB' }],
    series: [
      { name: '虚拟机数量', type: 'bar', data: rows.map(x => x.vm_count) },
      { name: 'CPU合计', type: 'line', smooth: true, data: rows.map(x => x.cpu_cores) },
      { name: '内存合计(GB)', type: 'line', yAxisIndex: 1, smooth: true, data: rows.map(x => x.memory_gb) }
    ]
  });
  c.on('click', p => { location.href = vmLink(group, p.name, snapshotId); });
}

async function initDashboard() {
  if (!document.getElementById('clusterChart')) return;
  const response = await fetch('/api/dashboard');
  const data = await response.json();
  if (!data.snapshot) return;
  const snapshotId = data.snapshot.id;
  renderCluster(data);
  renderDatastore(data);
  renderPie('osChart', data.os_groups, 'os', snapshotId);
  renderTrend('yearChart', data.yearly, 'year', snapshotId);
  renderTrend('monthChart', data.monthly, 'month', snapshotId);
  renderPie('primaryDeptChart', data.primary_departments, 'primary_department', snapshotId);
  renderPie('secondaryDeptChart', data.secondary_departments, 'secondary_department', snapshotId);
  window.addEventListener('resize', () => document.querySelectorAll('.chart').forEach(el => echarts.getInstanceByDom(el)?.resize()));
}

initDashboard();
