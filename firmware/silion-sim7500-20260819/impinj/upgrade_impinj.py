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
def IsImpinjAppFileName(bin_base_name):return bin_base_name.lower().startswith('ex10_app') and not has_any_keyword(bin_base_name,['MiniTP','MINI','贴片','SMD','SIMx100','SMP','mac','SIM','SQM','fdw'])
def CheckBinFileMatchForImpinjUpgrade(BinFileName,ImpinjFileInfo):
	BinBaseName=os.path.basename(BinFileName)
	if ImpinjFileInfo["版本"]=='未知':
		print(f'警告:MD5校验失败，文件名:{BinBaseName}')
		pause()
	if not IsImpinjAppFileName(BinBaseName):
		print(f'警告:当前脚本只能升级英频杰芯片固件,所选文件名不是ex10_app开头:'+BinBaseName)
		pause()

def GetImpinjVersionFromModule(rdr,P=True):
	DataTransport(rdr,build_command(0xAA04,[0xE7,0x00,0x00,0x00,0x23,0x00,0x00,0x00,0x00]))
	read_msg=DataReceive(rdr)
	if len(read_msg)>19 and read_msg[2]==0xAA and check_zero(read_msg[3:5])and read_msg[15]==0xAA and read_msg[16]==0x04:
		ImpinjVersionBytes=bytes(read_msg[17:-2]).split(b'\x00',1)[0]
		try:
			ImpinjVersion=ImpinjVersionBytes.decode('ascii')
		except UnicodeDecodeError:
			ImpinjVersion=Bytes2HEX(ImpinjVersionBytes,sep='')
		if P:print('模块内英频杰芯片版本:'+ImpinjVersion)
		return ImpinjVersion
	print('获取模块内英频杰芯片版本失败 read_msg:'+Bytes2HEX(read_msg,sep=' '))
	return'未知'

def AA54write(ImpinjFileInfo):
	with open(BinFileName,'rb')as f:
		print('AA54write open file:'+BinFileName)
		fr=f.read()
		len_fr=len(fr)
		if len_fr%4:
			print(f"文件长度不是4的倍数，长度为{len_fr}")
		cmd_times=math.ceil(len_fr/228)
		print(f'{ImpinjFileInfo["俗称"]}({ImpinjFileInfo["字节数"]}字节)文件大小={len_fr}字节,cmd_times={cmd_times}')
		print('请检查<型号(序列号)+连接方式+打开的文件>，确保连接稳定，确认升级请按任意键，不升级请关闭窗口!!!')
		pause()
		with alive_bar(cmd_times)as bar:
			for i in range(cmd_times):
				cmd=build_command(0xAA54,bytes([i!=0])+fr[i*228:i*228+228])
				if i==cmd_times-1 or i==0:print("send:"+Bytes2HEX(cmd,sep=''))
				for _ in range(3):
					send_time=time.perf_counter()
					DataTransport(rdr,cmd)
					read_msg=DataReceive(rdr)#FF 0C AA 00 00 4D 6F 64 75 6C 65 74 65 63 68 AA 54 0F 3F
					# print(f'{i} read_msg:'+Bytes2HEX(read_msg,sep=' '))
					if not read_msg:
						costtime="%.3fms"%((time.perf_counter()-send_time)*1000)
						print(f'耗费{costtime}:升级过程中{_}无回应{i} cmd:'+Bytes2HEX(cmd,sep=''))
						continue
					if len(read_msg)>=7 and check_zero(read_msg[3:5]):
						bar()
						break
					costtime="%.3fms"%((time.perf_counter()-send_time)*1000)
					print(f'耗费{costtime}:升级过程中收到错误码，需整体重新升级{i} cmd:'+Bytes2HEX(cmd,sep=''))
					print(f'耗费{costtime}:升级过程中收到错误码{i} read_msg:'+Bytes2HEX(read_msg,sep=''))
					rdr.close()
					return False
				else:#连续3次都没有回应
					print(f'当前分包{i}连续3次无回应，本次升级失败，将重新开始整体升级',flush=True)
					# pause()
					rdr.close()
					return False
				# if not i%100:print(f'{i}/{cmd_times}')
		settimeout(rdr,5)
		start_AA54FF_time=time.perf_counter()
		DataTransport(rdr,build_command(0xAA54,b'\xFF'))
		print('最后一步，已发送AA 54 FF，等待接收')
		read_msg=DataReceive(rdr)#FF 0C AA 00 00 4D 6F 64 75 6C 65 74 65 63 68 AA 54 0F 3F
		if len(read_msg)>=7 and check_zero(read_msg[3:5]):
			print('AA 54 FF接收成功,耗费:%.3fms'%((time.perf_counter()-start_AA54FF_time)*1000))
		else:
			print('AA 54 FF五秒接收失败 read_msg:'+Bytes2HEX(read_msg,sep=' '))
			rdr.close()
			pause()
			sys.exit(1)
		print('升级完成',end='',flush=True)
		return True

if __name__=='__main__':
	while True:
		rdr=Create(input("请输入读写器地址(可留空自动搜索):"))
		if not rdr:continue
		main_file_info=get_main_file_info()
		main_dir=main_file_info["main_dir"]#（如 C:\test）
		main_filename=main_file_info["main_filename"]#（如 main.py / main.exe）
		main_full_path=main_file_info["main_full_path"]#（如 C:\test\main.py）
		files=sorted(os.listdir(main_dir))
		# 当前在APP:进入BOOT+打印+进入APP+打印
		# 当前在BOOT:进入BOOT+打印+进入APP+打印
		# 无论在什么状态，都含真实的从BOOT->APP，所以无需用到Powermode三行代码
		SwitchToBOOTLayer(rdr,P=True)
		print("模块名称:"+GetModuleName(rdr,P=True),end=',',flush=True)
		print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
		SwitchToAPPLayer(rdr,P=True)
		print("模块名称:"+GetModuleName(rdr,P=True),end=',',flush=True)
		print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
		"""
		# 当前在APP:打印
		# 此时可能处于待机低功耗，所以需要用到Powermode三行代码
		# 当前在BOOT:打印+进入APP+打印
		print("模块名称:"+GetModuleName(rdr,P=True),end=',',flush=True)
		print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
		if 0x11==GetLayer(rdr,P=False):
			SwitchToAPPLayer(rdr,P=True)
			print("模块名称:"+GetModuleName(rdr,P=True),end=',',flush=True)
			print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
		"""
		
		for in_file in files:
			if os.path.splitext(in_file)[1].lower()=='.bin':
				BinFileName=main_dir+in_file
				break
		else:
			print(f'目录"{main_dir}"下没有bin文件')
			BinFileName=input('拖入英频杰芯片固件:').strip('"').strip("'")
			if not BinFileName:
				print(f'未拖入文件，即将退出')
				pause()
				ConnectionName=GetConnectionName(rdr)
				rdr.close()
				print('已断开'+ConnectionName+'的连接\n')
				continue
		ImpinjFileInfo=GetImpinjFileInfo(BinFileName)
		ModuleImpinjVersionBeforeUpgrade=GetImpinjVersionFromModule(rdr,P=False)
		print(f'选中文件英频杰芯片版本:{ImpinjFileInfo["版本"]},模块当前英频杰芯片版本:{ModuleImpinjVersionBeforeUpgrade}版本'+('相同，可能无需升级' if ImpinjFileInfo["版本"]==ModuleImpinjVersionBeforeUpgrade else'不相同，可以升级'))
		CheckBinFileMatchForImpinjUpgrade(BinFileName,ImpinjFileInfo)
		# Powermode=GetStandbyPowermode(rdr,P=False)
		# if Powermode in(2,3):SetStandbyPowermode(rdr,0,P=False)
		# AA54write()
		upgrade_start_time=time.perf_counter()
		upgrade_success=AA54write(ImpinjFileInfo)
		print("耗费:%.3fs"%(time.perf_counter()-upgrade_start_time))
		if not upgrade_success:continue
		SwitchToBOOTLayer(rdr,P=True)
		print("模块名称:"+GetModuleName(rdr,P=True),end=',',flush=True)
		print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
		SwitchToAPPLayer(rdr,P=True)
		print("模块名称:"+GetModuleName(rdr,P=True),end=',',flush=True)
		print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
		# if Powermode in(2,3):SetStandbyPowermode(rdr,Powermode,P=False)
		ModuleImpinjVersion=GetImpinjVersionFromModule(rdr,P=False)
		VersionMatchText=''if ImpinjFileInfo["版本"]==ModuleImpinjVersion else'不'
		ConnectionName=GetConnectionName(rdr)
		rdr.close()
		print(('失败'if VersionMatchText else'成功')+f'升级{ImpinjFileInfo["俗称"]}英频杰芯片固件完成({ImpinjFileInfo["版本"]}名称{VersionMatchText}一致{ModuleImpinjVersion})，已断开{ConnectionName}的连接\n')
