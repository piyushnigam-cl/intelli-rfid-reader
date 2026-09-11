from ModuleAPI import *

def CHECK_Firmware(BinFileName):
	with open(BinFileName,'rb')as f:
		print('CHECK_Firmware opened file:'+BinFileName)
		fr=f.read()
		len_fr=len(fr)
		if len_fr%4:
			print(f"文件长度不是4的倍数，长度为{len_fr}")
		CHECKDATA_LEN=len_fr//4
		CHECKCRC=[0x00,0x00,0x00,0x00]
		for i in range(len_fr):
			CHECKCRC[i%4]=(CHECKCRC[i%4]+fr[i])&0xFF
		cmd=build_command(0x08,STARTADDR.to_bytes(4,'big')+CHECKDATA_LEN.to_bytes(4,'big')+bytes(CHECKCRC))
		# print(','.join(['0x%02X'%i for i in cmd]))
		print(f'CHECK_Firmware cmd:'+Bytes2HEX(cmd,sep=' '))
		DataTransport(rdr,cmd)#FF 0C 08 08 00 80 00 00 00 A7 03 87 FD 36 4D C2 A9
		read_msg=DataReceive(rdr)#FF 00 08 00 00 05 C8
		print('Successful CHECK_Firmware'if len(read_msg)>=7 and check_zero(read_msg[3:5])else'Error CHECK_Firmware')
		print(f'CHECK_Firmware read_msg:'+Bytes2HEX(read_msg,sep=' '))
		return len(read_msg)>=7 and check_zero(read_msg[3:5])
def removeFF(APPFirmware):
	APPFirmwareList=list(APPFirmware)
	while len(APPFirmwareList)>=4 and set(APPFirmwareList[-4:])=={0xff}:
		del(APPFirmwareList[-4:])
	return bytes(APPFirmwareList)
def read_flash():
	with open(BinFileName,'wb')as f:
		print('正在写入文件:'+BinFileName)
		READADDR=STARTADDR
		i=0
		APPFirmware=b''
		while True:
			DataTransport(rdr,build_command(0x02,READADDR.to_bytes(4,'big')+bytes([32])))
			read_msg=DataReceive(rdr)#FF 00 01 00 00 94 E1
			# print(f'{i} read_msg:'+Bytes2HEX(read_msg,sep=' '))
			if len(read_msg)>=7 and check_zero(read_msg[3:5]):
				READADDR+=32*4
				# if i==0:print(f'读取到{i} read_msg:'+Bytes2HEX(read_msg,sep=' '))
				if (len(read_msg)-7)%4:
					print(f"数据长度不是4的倍数，长度为{len(read_msg)-7}，跳出")
					print(f'读取到 read_msg:'+Bytes2HEX(read_msg,sep=' '))
					rdr.close()
					pause()
					sys.exit(1)
				if set(read_msg[5:-2])=={0xff}:
					break
				else:
					APPFirmware+=read_msg[5:-2]
			else:
				print(f'读取过程中失败{i} read_msg:'+Bytes2HEX(read_msg,sep=' '))
				rdr.close()
				pause()
				sys.exit(1)
			if not i%100:print(f'读取到{i}')
			i+=1
		APPFirmware=removeFF(APPFirmware)
		f.write(APPFirmware)
		print(f'读取完成{len(APPFirmware)//1024}KB({len(APPFirmware)}字节)，文件存放在:'+BinFileName)

if __name__=='__main__':
	main_file_info=get_main_file_info()
	main_dir=main_file_info["main_dir"]#（如 C:\test）
	main_filename=main_file_info["main_filename"]#（如 main.py / main.exe）
	main_full_path=main_file_info["main_full_path"]#（如 C:\test\main.py）
	while True:
		rdr=Create(input("请输入读写器地址(可留空自动搜索):"))
		if not rdr:continue
		try:
			if 0x12==GetLayer(rdr,P=False):
				ModuleName=GetModuleName(rdr,P=True)
				print("模块名称:"+ModuleName,end=',',flush=True)
				print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
				SwitchToBOOTLayer(rdr,P=True)
				print("模块名称:"+GetModuleName(rdr,P=True),end=',',flush=True)
				print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
			else:#为BOOT层，若,80结尾，则用户选择是否是完整的APP
				ModuleName=GetModuleName(rdr,P=True)
				print("模块名称:"+ModuleName,end=',',flush=True)
				print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
				if ModuleName.endswith('80'):
					if input("在BOOT获取到硬件版本尾号80\n不读取准确名称而提取固件(APP可能损坏)→直接回车\n进入APP获取模块名称(APP完整)→输入1并回车:"):
						SwitchToAPPLayer(rdr,P=True)
						ModuleName=GetModuleName(rdr,P=True)
						print("模块名称:"+ModuleName,end=',',flush=True)
						print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
						SwitchToBOOTLayer(rdr,P=True)
						print("模块名称:"+GetModuleName(rdr,P=True),end=',',flush=True)
						print("模块序列号:"+GetModuleSerialNumber(rdr,P=False))
			#旗连0x08003000，英频杰R2000系列0x00104000，复旦微/英频杰E系列0x08008000
			if 'SQM5400'in ModuleName:STARTADDR=0x08008000;print(f'SQM5400,STARTADDR={STARTADDR:0>8X}')
			elif ModuleName[:3]=="SQM"or ModuleName=="SLR5200":STARTADDR=0x08003000;print(f'旗连,STARTADDR={STARTADDR:0>8X}')
			elif ModuleName[:3]=="SLR"and ModuleName!="SLR5200":STARTADDR=0x00104000;print(f'R2000,STARTADDR={STARTADDR:0>8X}')
			elif ModuleName[:2]in("E7","E5","E3","E9","FM"):STARTADDR=0x08008000;print(f'E7/E5/E3/E9/FM,STARTADDR={STARTADDR:0>8X}')
			elif ModuleName[:3]in("SIM","SFM","FDM"):STARTADDR=0x08008000;print(f'SIM/SFM/FDM,STARTADDR={STARTADDR:0>8X}')
			else:STARTADDR=0x08008000;print(f'else,STARTADDR={STARTADDR:0>8X}')
			DataTransport(rdr,b'\xFF\x00\x03\x1D\x0C')
			read_msg=DataReceive(rdr)[13:13+4]
			BinFileName=os.path.join(main_dir,ModuleName+'_'+Bytes2HEX(read_msg,sep='')+'_'+datetime.datetime.today().strftime('%Y-%m-%d_%H.%M.%S.%f')[:-3]+'.bin')
			print("耗费:%.3fs"%timeit.timeit(stmt=read_flash,number=1))
			CHECK_Firmware(BinFileName)
		finally:
			try:ConnectionName=GetConnectionName(rdr)
			except Exception:ConnectionName=''
			try:rdr.close()
			except Exception:pass
			if ConnectionName:print('已断开'+ConnectionName+'的连接\n')
