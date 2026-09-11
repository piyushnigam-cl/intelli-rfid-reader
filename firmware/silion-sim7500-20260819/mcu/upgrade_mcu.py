import timeit,math
try:
	from alive_progress import alive_bar
except ImportError as alive_progress_error:
	from contextlib import contextmanager
	print(f"警告：导入{getattr(alive_progress_error,'name','alive_progress')}失败:{alive_progress_error}，自动使用内置文本进度条")
	@contextmanager
	def alive_bar(total):
		current=[0]
		print(f'进度:0/{total} 0.00%',end='',flush=True)
		def bar():
			current[0]+=1
			percent=current[0]*100/total if total else 100
			print(f'\r进度:{current[0]}/{total} {percent:.2f}%',end=''if current[0]<total else'\n',flush=True)
		try:
			yield bar
		finally:
			if current[0]<total:print()
from ModuleAPI import *
def has_any_keyword(text,keywords):return any(keyword.lower()in text.lower()for keyword in keywords)
def IsMiniTPFileName(bin_base_name):return has_any_keyword(bin_base_name,['MiniTP','MINI','贴片','SMD']) and not has_any_keyword(bin_base_name,['SIMx100','SMP','ex10_app','SQM','mac','fdw'])
def IsSIMx100FileName(bin_base_name):return has_any_keyword(bin_base_name,['SIMx100','SMP']) and not has_any_keyword(bin_base_name,['MiniTP','MINI','贴片','SMD','ex10_app','SQM','mac','fdw'])
def IsFudanFileName(bin_base_name):return has_any_keyword(bin_base_name,['mac','fdw']) and not has_any_keyword(bin_base_name,['MiniTP','MINI','贴片','SMD','SIMx100','SMP','ex10_app','SQM','SIM'])
def IsQilianFileName(bin_base_name):return bin_base_name.upper().startswith('SQM') and not has_any_keyword(bin_base_name,['MiniTP','MINI','贴片','SMD','SIMx100','SMP','ex10_app','mac','SIM','fdw'])
def IsImpinjAppFileName(bin_base_name):return bin_base_name.lower().startswith('ex10_app') and not has_any_keyword(bin_base_name,['MiniTP','MINI','贴片','SMD','SIMx100','SMP','mac','SIM','SQM','fdw'])
def replace_SIM3579_SIMx(ModuleName):return ModuleName.replace('SIM3','SIMx').replace('SIM5','SIMx').replace('SIM7','SIMx').replace('SIM9','SIMx')
def NeedMiniTPFirmware(ModuleName,FirstInAPP=False):
	if FirstInAPP:
		return replace_SIM3579_SIMx(ModuleName)in ['SIMx700','SIMx600旧','SIMx800旧','含SIMx900旧','SIMx600新','SIMx800新','SIMx900新','SIMx500新','SIMx110']
	else:#一开始就在BOOT
		if APPHardwareVersion[-1]==0x80:
			return True
		else:
			return replace_SIM3579_SIMx(ModuleName)in ['SIMx700','SIMx600旧','SIMx110']
def CheckBinFileMatchForMcuUpgrade(ModuleName,device_type,BinFileName,FirstInAPP=False):
	BinBaseName=os.path.basename(BinFileName)
	WarningText=''
	if device_type=='FUDAN':
		if not IsFudanFileName(BinBaseName):WarningText='当前模块判定为复旦微,但所选文件名不像复旦微固件(mac开头)'
	elif device_type=='QILIAN':
		if not IsQilianFileName(BinBaseName):WarningText='当前模块判定为旗连,但所选文件名不像旗连固件(SQMxxxx.bin)'
	else:#其他类型"IMPINJ"和"R2000"和""
		if IsImpinjAppFileName(BinBaseName):WarningText='当前脚本是模块单片机固件升级,但所选文件像英频杰芯片固件(ex10_app开头)'
		else:
			NeedMiniTP=NeedMiniTPFirmware(ModuleName,FirstInAPP)
			if NeedMiniTP and not IsMiniTPFileName(BinBaseName):WarningText='当前模块更像应使用MiniTP/MINI/贴片/SMD字样固件,但所选文件名不匹配'
			elif(not NeedMiniTP)and not IsSIMx100FileName(BinBaseName):WarningText='当前模块更像应使用SIMx100/SMP字样固件,但所选文件名不匹配'
	if WarningText:
		print('警告:'+WarningText+'，请再次检查文件是否正确，不升级请关闭窗口')
		pause()
def CHECK_Firmware(BinFileName):
	with open(BinFileName,'rb')as f:
		print('CHECK_Firmware open file:'+BinFileName)
		fr=f.read()
		len_fr=len(fr)
		if len_fr%4:
			print(f"文件长度不是4的倍数，长度为{len_fr}")
		CHECKDATA_LEN=len_fr//4
		CHECKCRC=[0x00,0x00,0x00,0x00]
		for i in range(len_fr):
			CHECKCRC[i%4]=(CHECKCRC[i%4]+fr[i])&0xFF
		cmd=build_command(0x08,STARTADDR.to_bytes(4,'big')+CHECKDATA_LEN.to_bytes(4,'big')+bytes(CHECKCRC))
		# print(Bytes2HEX(cmd,sep=','))
		DataTransport(rdr,cmd)#FF 0C 08 08 00 80 00 00 00 A7 03 87 FD 36 4D C2 A9
		read_msg=DataReceive(rdr)#FF 00 08 00 00 05 C8
		CHECK_Firmware_Successful=len(read_msg)>=7 and check_zero(read_msg[3:5])
		if CHECK_Firmware_Successful:
			print('Successful CHECK_Firmware')
		else:
			print('Error CHECK_Firmware')
			print(f'CHECK_Firmware cmd:'+Bytes2HEX(cmd,sep=' '))
			print(f'CHECK_Firmware read_msg:'+Bytes2HEX(read_msg,sep=' '))
		return CHECK_Firmware_Successful
def write_flash():
	with open(BinFileName,'rb')as f:
		print('write_flash open file:'+BinFileName)
		fr=f.read()
		len_fr=len(fr)
		if len_fr%4:
			print(f"文件长度不是4的倍数，长度为{len_fr}")
		WRITEADDR=STARTADDR
		total_WRITELEN=len_fr//4
		cmd_times=math.ceil(len_fr/128)
		print(f'文件大小={len_fr}字节,total_WRITELEN={total_WRITELEN}')
		print('请检查<型号(序列号)+连接方式+打开的文件>，确保连接稳定，确认升级请按任意键，不升级请关闭窗口!!!')
		pause()
		with alive_bar(cmd_times)as bar:
			for i in range(cmd_times):
				if total_WRITELEN>=32:
					WRITELEN=32
					total_WRITELEN-=WRITELEN
				else:
					WRITELEN=total_WRITELEN
				cmd=build_command(0x01,bytes([0xFF if i==cmd_times-1 else 0x00])+WRITEADDR.to_bytes(4,'big')+bytes([WRITELEN])+fr[i*128:i*128+128])
				if i==cmd_times-1 or i==0:print("send:"+Bytes2HEX(cmd,sep=''))
				for _ in range(3):
					send_time=time.perf_counter()
					DataTransport(rdr,cmd)
					read_msg=DataReceive(rdr)#FF 00 01 00 00 94 E1
					# print(f'{i} read_msg:'+Bytes2HEX(read_msg,sep=' '))
					if len(read_msg)>=7 and check_zero(read_msg[3:5]):
						WRITEADDR+=WRITELEN*4
						bar()
						break
					else:
						costtime="%.3fms"%((time.perf_counter()-send_time)*1000)
						print(f'耗费{costtime}:升级过程中{_}失败{i} cmd:'+Bytes2HEX(cmd,sep=''))
						print(f'耗费{costtime}:升级过程中{_}失败{i} read_msg:'+Bytes2HEX(read_msg,sep=''))
				else:
					print('升级失败，即将退出',end='',flush=True)
					# pause()
					rdr.close()
					return
				# if not i%100:print(f'{i}/{cmd_times}')
		print('升级完成',end='',flush=True)

if __name__=='__main__':
	while True:
		rdr=Create(input("请输入读写器地址(可留空自动搜索):"))
		if not rdr:continue
		main_file_info=get_main_file_info()
		main_dir=main_file_info["main_dir"]#（如 C:\test）
		main_filename=main_file_info["main_filename"]#（如 main.py / main.exe）
		main_full_path=main_file_info["main_full_path"]#（如 C:\test\main.py）
		files=sorted(os.listdir(main_dir))
		if 0x12==GetLayer(rdr,P=False):
			FirstInAPP=True
			ModuleName=GetModuleName(rdr,P=True)
			print("模块名称:"+ModuleName,end=',',flush=True)
			print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
			SwitchToBOOTLayer(rdr,P=True)
			print("模块名称:"+GetModuleName(rdr,P=True),end=',',flush=True)
			print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
		else:
			FirstInAPP=False
			APPHardwareVersion=GetHardwareVersion(rdr,P=False)
			ModuleName=GetModuleName(rdr,P=True)
			print("模块名称:"+ModuleName,end=',',flush=True)
			print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
		
		#复旦微0x08008000，与E系列相同，即80结尾的复旦微也可以被判定为E系列
		#旗连SQM5800=0x08008000
		#旗连0x08003000
		#英频杰R2000系列0x00104000
		#英频杰E系列0x08008000
		if ModuleName[:3]in("SFM","FDM"):STARTADDR=0x08008000;print(f'SFM/FDM,STARTADDR={STARTADDR:0>8X}');device_type='FUDAN'
		elif ModuleName[:2]in("FM"):STARTADDR=0x08008000;print(f'FM,STARTADDR={STARTADDR:0>8X}');device_type='FUDAN'
		elif ModuleName=="SQM5800":STARTADDR=0x08008000;print(f'SQM5800,STARTADDR={STARTADDR:0>8X}');device_type='QILIAN'
		elif ModuleName[:3]=="SQM"or ModuleName=="SLR5200":STARTADDR=0x08003000;print(f'旗连,STARTADDR={STARTADDR:0>8X}');device_type='QILIAN'
		elif ModuleName[:3]=="SLR"and ModuleName!="SLR5200":STARTADDR=0x00104000;print(f'R2000,STARTADDR={STARTADDR:0>8X}');device_type='R2000'
		elif ModuleName[:3]in("SIM"):STARTADDR=0x08008000;print(f'SIM,STARTADDR={STARTADDR:0>8X}');device_type='IMPINJ'
		elif ModuleName[:2]in("E7","E5","E3","E9"):STARTADDR=0x08008000;print(f'E7/E5/E3/E9,STARTADDR={STARTADDR:0>8X}');device_type='IMPINJ'
		else:STARTADDR=0x08008000;print(f'else,STARTADDR={STARTADDR:0>8X}');device_type=''
		for in_file in files:
			if os.path.splitext(in_file)[1].lower()=='.bin':
				BinFileName=main_dir+in_file
				break
		#写Flash 0x01
		# write_flash()
		else:
			print(f'目录"{main_dir}"下没有bin文件')
			BinFileName=input('拖入模块单片机固件:').strip('"').strip("'")
			if not BinFileName:
				print(f'未拖入文件，即将退出')
				pause()
				ConnectionName=GetConnectionName(rdr)
				rdr.close()
				print('已断开'+ConnectionName+'的连接\n')
				continue
		CheckBinFileMatchForMcuUpgrade(ModuleName,device_type,BinFileName,FirstInAPP)
		print("耗费:%.3fs"%timeit.timeit(stmt=write_flash,number=1))
		
		#校验Firmware 0x08
		if CHECK_Firmware(BinFileName):
			start_SwitchToAPPLayer_time=time.perf_counter()
			# print("settimeout(rdr,5)",start_SwitchToAPPLayer_time)
			if SwitchToAPPLayer(rdr,timeout=5,P=True)==0x12:
				print("首次进入APP Successful,耗费:%.3fms"%((time.perf_counter()-start_SwitchToAPPLayer_time)*1000))
				print("模块名称:"+GetModuleName(rdr,P=True),end=',',flush=True)
				print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
			else:
				print("首次进入APP Error,耗费:%.3fms"%((time.perf_counter()-start_SwitchToAPPLayer_time)*1000))
		ConnectionName=GetConnectionName(rdr)
		rdr.close()
		print('写Flash升级更新固件APP应用层完成，已断开'+ConnectionName+'的连接\n')
r"""
林工给的型号表中提取:
//R2000
A0000001:SLR1100
A1000001:SLR1200
A1000201:SLR1200V2
A1000203:SLR1200V2-0001
A1030201:SLR1200V2
A1000202:SLR1219
A0000201:SLR5600
A8000000:SLR5800
A8000001:SLR5800-0001
A9000000:SLR5900
A9000001:SLR5900-0001
AA000000:SLR6000
AA000001:SLR6000-0001
AB000000:SLR6100
AB000001:SLR6100-0001

//旗连
A4000000:SLR5200
A4000300:SQM5400
A4000380:SQM5400
A4000321:SQM5400V2
A4000322:SQM5400V3
AC002000:SQMM120
AC002001:SQMM120-0020
AC011100:SQMM126
AC011101:SQMM126-0020
A4000500:SQM5500
A4000521:SQM5500V2
A6000200:SQM5100
A6000201:SQM5300
A6000220:SQM5300V1
A6000221:SQM5300V2

//复旦微
B1000000:SFM2100
B3000000:FDMA100
B1020000:SFM2200
B3020000:FDMA200
B1030000:SFM2300
B3030000:FDMA300
B1040000:SFM2400
B3040000:FDMA400
B1100000:SFM2500
B3100000:FDMA500

//E系列
以31/32/33/34开头

java源码中的升级地址
response[9]
default:0010a000
00:0010a000//是哪几款？
01:0010a000//是哪几款？
02:0010a000//是哪几款？
18:0010a000//是哪几款？
19:0010a000//是哪几款？
20:0010a000//是哪几款？

A0:00104000//R2000
A1:00104000//R2000
A8:00104000//R2000
A9:00104000//R2000
AA:00104000//是哪几款？
AB:00104000//是哪几款？

A2:08003000//是哪几款？
A3:08003000//是哪几款？
A4:08003000//旗连
A5:08003000//是哪几款？
A6:08003000//旗连
A7:08003000//是哪几款？
AC:没加进去？SQMM120/SQMM126

31:08008000//E系列
32:08008000//E系列
33:08008000//E系列
34:08008000//E系列
B1:没加进去？复旦微
B3:没加进去？复旦微
FF:08008000
"""
