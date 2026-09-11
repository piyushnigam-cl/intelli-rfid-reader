import sys,os,time,math
from ModuleAPI import *
if __name__=='__main__':
	while True:
		rdr=Create(input("请输入读写器地址(可留空自动搜索):"))
		if not rdr:continue
		SwitchToAPPLayer(rdr,P=True)
		print("模块名称:"+GetModuleName(rdr,P=False),end=',',flush=True)
		print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
		
		# 获取上电时默认是否上电运行至APP
		cmd=build_command(0xAA40,[4,0])
		print(f'获取cmd:'+Bytes2HEX(cmd,sep=' '))
		DataTransport(rdr,cmd)
		read_msg=DataReceive(rdr)#FF 12 AA 00 00 4D 6F 64 75 6C 65 74 65 63 68 AA 40 04 00 A5 A5 5A 5A DD 67或FF 12 AA 00 00 4D 6F 64 75 6C 65 74 65 63 68 AA 40 04 00 00 00 00 00 80 F9
		print('成功'if len(read_msg)>=7 and check_zero(read_msg[3:5])else'失败',end='',flush=True)
		print('获取上电时默认是否上电运行至APP read_msg:'+Bytes2HEX(read_msg[-6:-2]),end='',flush=True)#A5 A5 5A 5A或00 00 00 00
		print("~"*5+('自动'if read_msg[-6:-2]==bytes.fromhex('A5A55A5A')else'不自动')+"~"*5)
		
		# 设置上电时默认上电是否运行至APP
		if input("不自动→直接回车\n自动→输入1并回车:"):
			cmd=build_command(0xAA40,[4,1]+list(bytes.fromhex('A5A55A5A')))#自动运行至APP
		else:
			cmd=build_command(0xAA40,[4,1]+[0]*4)#不自动运行至APP
		print(f'设置cmd:'+Bytes2HEX(cmd,sep=' '))
		DataTransport(rdr,cmd)
		read_msg=DataReceive(rdr)#FF 0E AA 00 00 4D 6F 64 75 6C 65 74 65 63 68 AA 40 04 01 C1 5F
		print('成功'if len(read_msg)>=7 and check_zero(read_msg[3:5])else'失败',end='',flush=True)
		print('设置上电时默认'+"~"*5+('自动'if cmd[-8:-4]==bytes.fromhex('A5A55A5A')else'不自动')+"~"*5+'上电运行至APP read_msg:'+Bytes2HEX(read_msg,sep=' '))
		
		# 获取上电时默认是否上电运行至APP
		cmd=build_command(0xAA40,[4,0])
		print(f'获取cmd:'+Bytes2HEX(cmd,sep=' '))
		DataTransport(rdr,cmd)
		read_msg=DataReceive(rdr)#FF 12 AA 00 00 4D 6F 64 75 6C 65 74 65 63 68 AA 40 04 00 A5 A5 5A 5A DD 67或FF 12 AA 00 00 4D 6F 64 75 6C 65 74 65 63 68 AA 40 04 00 00 00 00 00 80 F9
		print('成功'if len(read_msg)>=7 and check_zero(read_msg[3:5])else'失败',end='',flush=True)
		print('获取上电时默认是否上电运行至APP read_msg:'+Bytes2HEX(read_msg[-6:-2]),end='',flush=True)#A5 A5 5A 5A或00 00 00 00
		print("~"*5+('自动'if read_msg[-6:-2]==bytes.fromhex('A5A55A5A')else'不自动')+"~"*5)
		
		SwitchToBOOTLayer(rdr,PreparingUpgrade=False,P=True)
		GetLayer(rdr,P=True)
		ConnectionName=GetConnectionName(rdr)
		rdr.close()
		print('已断开'+ConnectionName+'的连接\n')
"""
自动运行至APP:
	AB+09:BOOT
	09:APP
不自动运行至APP:
	AB+09:BOOT
	09:BOOT
"""