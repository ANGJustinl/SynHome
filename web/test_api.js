// 测试设备模拟服务器API连接
const API_BASE = 'http://localhost:8000';

async function testAPI() {
    console.log('🔍 测试SynHome设备模拟服务器API...');

    try {
        // 测试获取设备列表
        console.log('\n📱 测试设备列表获取...');
        const devicesResponse = await fetch(`${API_BASE}/devices`);
        const devicesData = await devicesResponse.json();

        if (devicesResponse.ok) {
            console.log('✅ 成功获取设备列表');
            console.log(`   设备总数: ${devicesData.count}`);
            console.log('   设备详情:');
            devicesData.devices.forEach((device, index) => {
                console.log(`   ${index + 1}. ${device.name} (${device.device_type}) - ${device.online ? '在线' : '离线'}`);
            });
        } else {
            console.log('❌ 获取设备列表失败');
        }

        // 测试设备控制
        if (devicesData.devices && devicesData.devices.length > 0) {
            const firstDevice = devicesData.devices[0];
            console.log(`\n🎮 测试设备控制: ${firstDevice.name}`);

            const controlResponse = await fetch(`${API_BASE}/devices/${firstDevice.device_id}/command`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    device_id: firstDevice.device_id,
                    capability: 'power',
                    value: 'on'
                })
            });

            const controlData = await controlResponse.json();

            if (controlResponse.ok && controlData.success) {
                console.log('✅ 设备控制成功');
                console.log(`   设备: ${controlData.device_id}`);
                console.log(`   能力: ${controlData.capability}`);
                console.log(`   结果: ${controlData.new_value}`);
            } else {
                console.log('❌ 设备控制失败');
                console.log(`   错误: ${controlData.message || '未知错误'}`);
            }
        }

        console.log('\n🎉 API测试完成！');

    } catch (error) {
        console.error('❌ API测试失败:', error.message);
    }
}

// 运行测试
testAPI();