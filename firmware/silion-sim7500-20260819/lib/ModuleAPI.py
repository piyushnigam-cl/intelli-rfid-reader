SERIAL_AVAILABLE=True# 手动开关，True则尝试导入串口库，导入失败会自动置False
TCP_AVAILABLE=True# 手动开关，True则尝试导入网口库，导入失败会自动置False
HID_AVAILABLE=True# 手动开关，True则尝试导入HID库，导入失败会自动置False
CTYPES_AVAILABLE=True# 手动开关，True则尝试导入Windows颜色依赖，导入失败会自动置False
PSUTIL_AVAILABLE=True# 手动开关，True则尝试导入Windows网卡搜索依赖，导入失败会自动置False
NETIFACES_AVAILABLE=True# 手动开关，True则尝试导入Windows网卡搜索依赖，导入失败会自动置False
FCNTL_AVAILABLE=True# 手动开关，True则尝试导入Linux网卡搜索依赖，导入失败会自动置False
WINREG_AVAILABLE=True# 手动开关，True则尝试导入Windows注册表依赖，导入失败会自动置False
try:
	import time,sys,os,re,datetime,threading,hashlib,ipaddress,weakref,timeit#===通用模块导入（始终需要）===
except ImportError as E:
	print(f"警告：ModuleAPI通用依赖导入失败，首个失败模块:{getattr(E,'name','未知模块')}，错误:{E}")
	os.system('pause')if sys.platform.startswith('win')else input('程序无法继续，请按回车退出...')
	sys.exit()
IS_WINDOWS=sys.platform.startswith('win')
IS_LINUX=sys.platform.startswith('linux')
IS_MACOS=sys.platform.startswith('darwin')
if IS_LINUX:HID_AVAILABLE=False#===Linux 不支持USB HID===后期有需要再开发
def pause():
	if IS_WINDOWS:
		os.system('pause')
		return
	while True:
		try:
			choice=input('是否继续[Y/n]:').strip().lower()
		except(EOFError,KeyboardInterrupt):
			print()
			sys.exit()
		if choice in('','y','yes'):return
		if choice in('n','no'):sys.exit()
		print('请输入Y或n')
if CTYPES_AVAILABLE and IS_WINDOWS:
	try:
		import ctypes
	except ImportError as E:
		CTYPES_AVAILABLE=False
		print(f"警告：Windows颜色依赖导入失败，首个失败模块:{getattr(E,'name','未知模块')}，错误:{E}，控制台颜色功能不可用")
else:CTYPES_AVAILABLE=False
if SERIAL_AVAILABLE:#===COM 串口模块条件导入===
	try:
		import serial
		from serial.tools import list_ports
	except ImportError as E:
		SERIAL_AVAILABLE=False
		print(f"警告：SERIAL_AVAILABLE=True 但导入{getattr(E,'name','未知模块')}失败:{E}，串口功能不可用")
if WINREG_AVAILABLE and SERIAL_AVAILABLE and IS_WINDOWS:
	try:
		import winreg
	except ImportError as E:
		WINREG_AVAILABLE=False
		print(f"警告：WINREG_AVAILABLE=True 但导入{getattr(E,'name','未知模块')}失败:{E}，不能用注册表搜索串口")
else:WINREG_AVAILABLE=False
if TCP_AVAILABLE:
	try:
		import socket
	except ImportError as E:
		TCP_AVAILABLE=False
		print(f"警告：TCP_AVAILABLE=True 但导入{getattr(E,'name','未知模块')}失败:{E}，网口功能不可用")
if PSUTIL_AVAILABLE and TCP_AVAILABLE and(IS_WINDOWS or IS_MACOS):
	try:
		import psutil
	except ImportError as E:
		PSUTIL_AVAILABLE=False
		print(f"警告：TCP_AVAILABLE=True 但导入{getattr(E,'name','未知模块')}失败:{E}，不能用psutil搜索本机网卡")
else:PSUTIL_AVAILABLE=False
if NETIFACES_AVAILABLE and TCP_AVAILABLE and(IS_WINDOWS or IS_MACOS):
	try:
		import netifaces
	except ImportError as E:
		NETIFACES_AVAILABLE=False
		print(f"警告：TCP_AVAILABLE=True 但导入{getattr(E,'name','未知模块')}失败:{E}，不能用netifaces搜索本机网卡")
else:NETIFACES_AVAILABLE=False
if FCNTL_AVAILABLE and TCP_AVAILABLE and IS_LINUX:
	try:
		import fcntl
	except ImportError as E:
		FCNTL_AVAILABLE=False
		print(f"警告：Linux网卡搜索依赖导入失败，首个失败模块:{getattr(E,'name','未知模块')}，错误:{E}，不能自动搜索本机网卡")
else:FCNTL_AVAILABLE=False
if HID_AVAILABLE:#===USB HID 模块条件导入===
	try:
		import hid
	except ImportError as E:
		HID_AVAILABLE=False
		print(f"警告：HID_AVAILABLE=True 但导入{getattr(E,'name','未知模块')}失败:{E}，USB HID 功能不可用")
MACOS_IP_BOUND_IF=getattr(socket,'IP_BOUND_IF',25)if TCP_AVAILABLE else 25
def bind_udp_socket_to_interface(udp_socket,interface_name):
	if IS_MACOS and interface_name and interface_name!='不绑定本机IP':
		udp_socket.setsockopt(socket.IPPROTO_IP,MACOS_IP_BOUND_IF,socket.if_nametoindex(interface_name))
def get_udp_bind_address(local_ip,local_port):
	return ('',local_port)if IS_MACOS else(local_ip,local_port)
_SUPPORTED_BAUDRATES=(9600,19200,38400,57600,115200,230400,460800,921600)
def _get_serial_auto_timeouts(baudrate):
	current_timeout=0.1 if IS_MACOS or baudrate<=115200 else 0.01
	if IS_MACOS:return current_timeout,0.1,0.1
	return current_timeout,current_timeout+0.5,None
_HID_DEFAULT_TIMEOUT=0.6#USB HID 超时时间单位s
_HID_STATES_LOCK=threading.RLock()
_HID_WEAK_STATES=weakref.WeakKeyDictionary()
_HID_FALLBACK_STATES={}

class _HidConnection:
	"""代理 hid.device，并在普通 close() 时清理该连接的接收状态。"""
	def __init__(self,device):
		self._device=device
	def __getattr__(self,name):
		return getattr(self._device,name)
	def close(self):
		try:
			return self._device.close()
		finally:
			_forget_hid_state(self)

def _new_hid_state():
	return {'buffer':b'','timeout':_HID_DEFAULT_TIMEOUT,'lock':threading.RLock()}

def _remove_fallback_hid_state(object_id,object_ref):
	with _HID_STATES_LOCK:
		entry=_HID_FALLBACK_STATES.get(object_id)
		if entry and entry[0]is object_ref:
			_HID_FALLBACK_STATES.pop(object_id,None)

def _get_hid_state(s):
	"""获取每个 HID 连接独立的缓存、超时和锁，并兼容简单 mock。"""
	with _HID_STATES_LOCK:
		try:
			state=_HID_WEAK_STATES.get(s)
			if state is None:
				state=_new_hid_state()
				_HID_WEAK_STATES[s]=state
			return state
		except TypeError:
			# 某些测试 mock 不可哈希或不可弱引用，按对象 id 隔离状态。
			object_id=id(s)
			entry=_HID_FALLBACK_STATES.get(object_id)
			if entry:
				current_object=entry[0]()if entry[2]else entry[0]
				if current_object is s:return entry[1]
			try:
				object_ref=weakref.ref(s,lambda ref,key=object_id:_remove_fallback_hid_state(key,ref))
				is_weak=True
			except TypeError:
				object_ref=s
				is_weak=False
			state=_new_hid_state()
			_HID_FALLBACK_STATES[object_id]=(object_ref,state,is_weak)
			return state

def _reset_hid_state(s):
	state=_get_hid_state(s)
	with state['lock']:
		state['buffer']=b''
		state['timeout']=_HID_DEFAULT_TIMEOUT
	return state

def _forget_hid_state(s):
	with _HID_STATES_LOCK:
		try:_HID_WEAK_STATES.pop(s,None)
		except TypeError:pass
		entry=_HID_FALLBACK_STATES.get(id(s))
		if entry:
			current_object=entry[0]()if entry[2]else entry[0]
			if current_object is s:_HID_FALLBACK_STATES.pop(id(s),None)
ModuleHardwareType={b'\xA0\x00\x00\x01':"SLR1100",b'\xA1\x00\x00\x01':"SLR1200",b'\xA1\x00\x02\x01':"SLR1200V2",b'\xA1\x00\x02\x03':"SLR1200V2-0001",b'\xA1\x03\x02\x01':"SLR1200V2",b'\xA1\x00\x02\x02':"SLR1219",b'\xA0\x00\x02\x01':"SLR5600",b'\xA8\x00\x00\x00':"SLR5800",b'\xA8\x00\x00\x01':"SLR5800-0001",b'\xA9\x00\x00\x00':"SLR5900",b'\xA9\x00\x00\x01':"SLR5900-0001",b'\xAA\x00\x00\x00':"SLR6000",b'\xAA\x00\x00\x01':"SLR6000-0001",b'\xAB\x00\x00\x00':"SLR6100",b'\xAB\x00\x00\x01':"SLR6100-0001",b'\xA4\x00\x00\x00':"SLR5200",b'\xA4\x00\x03\x00':"SQM5400",b'\xA4\x00\x03\x80':"SQM5400",b'\xA4\x00\x03\x21':"SQM5400V2",b'\xA4\x00\x03\x22':"SQM5400V3",b'\xAC\x00\x20\x00':"SQMM120",b'\xAC\x00\x20\x01':"SQMM120-0020",b'\xAC\x01\x11\x00':"SQMM126",b'\xAC\x01\x11\x01':"SQMM126-0020",b'\xA4\x00\x05\x00':"SQM5500",b'\xA4\x00\x05\x21':"SQM5500V2",b'\xA6\x00\x02\x00':"SQM5100",b'\xA6\x00\x02\x01':"SQM5300",b'\xA6\x00\x02\x20':"SQM5300V1",b'\xA6\x00\x02\x21':"SQM5300V2",b'\xC0\x00\x00\x01':"SQM5800",b'\xC0\x00\x00\x00':"SQM5800",b'\xB1\x00\x00\x00':"SFM2100",b'\xB3\x00\x00\x00':"FDMA100",b'\xB1\x02\x00\x00':"SFM2200",b'\xB3\x02\x00\x00':"FDMA200",b'\xB1\x03\x00\x00':"SFM2300",b'\xB3\x03\x00\x00':"FDMA300",b'\xB1\x04\x00\x00':"SFM2400",b'\xB3\x04\x00\x00':"FDMA400",b'\xB1\x10\x00\x00':"SFM2500",b'\xB3\x10\x00\x00':"FDMA500"}
CertificationRegionCodes={0x00:"CHINA",0x01:"FCC",0x02:"JAPAN_NOLBT_4FRE",0x03:"CE_LOW",0x04:"KOREA",0x05:"CE_HIGH",0x06:"HK",0x07:"TAIWAN",0x08:"MALAYSIA",0x09:"SOUTH_AFRICA",0x0A:"BRAZIL",0x0B:"THAILAND",0x0C:"SINGAPORE",0x0D:"AUSTRALIA",0x0E:"INDIA",0x0F:"URUGUAY",0x10:"VIETNAM",0x11:"ISRAEL",0x12:"PHILIPPINES",0x13:"INDONESIA",0x14:"NEW_ZEALAND",0x15:"PERU",0x16:"RUSSIA",0x18:"JAPAN_LBT_6FRE",0x19:"JAPAN_LBT_19FRE"}
#20260622删除0x17:"CE_LOW_AND_HIGH",0xA1:"FCC_CUSTOM",
#需要从API和demo以及文档层面，把"CE_LOW_AND_HIGH"和"FCC_CUSTOM"删了。是内部测试用的
FrequencyBandCodes={0x01:"NORTH_AMERICA",0x06:"CHINA",0x0A:"CHINA_SQM5400",0x05:"JAPAN_6FRE_SQM5400",0x08:"CE_LOW",0x09:"KOREA",0x0B:"JAPAN_NOLBT_4FRE",0x1F:"JAPAN_LBT_6FRE",0x20:"JAPAN_LBT_19FRE",0x0C:"CE_HIGH",0x0D:"HK",0x0E:"TAIWAN",0x0F:"MALAYSIA",0x10:"SOUTH_AFRICA",0x11:"BRAZIL",0x12:"THAILAND",0x13:"SINGAPORE",0x14:"AUSTRALIA",0x04:"INDIA",0x16:"URUGUAY",0x17:"VIETNAM",0x18:"ISRAEL",0x19:"PHILIPPINES",0x1A:"INDONESIA",0x1B:"NEW_ZEALAND",0x1C:"PERU",0x1D:"RUSSIA",0xFF:"FULL_FREQUENCY"}
ModuleTypeFirstBytes={b'\xA0':"SLR1100",b'\xA1':"SLR1200",b'\xA2':"SLR3000",b'\xA3':"SLR5100",b'\xA4':"SLR5200",b'\xA5':"SLR3100",b'\xA6':"SLR5300",b'\xA7':"SLR3200",b'\xA8':"SLR5800",b'\xA9':"SLR5900",b'\xAA':"SLR6000",b'\xAB':"SLR6100",b'\xAC':"SQMM120/SQMM126"}
FOREGROUND_COLOR={'透明':0x00,'暗蓝':0x01,'暗绿':0x02,'暗天蓝':0x03,'暗红':0x04,'暗粉':0x05,'暗黄':0x06,'暗白':0x07,'暗灰':0x08,'天蓝':0x0b,'蓝':0x09,'绿':0x0a,'红':0x0c,'粉':0x0d,'黄':0x0e,'白':0x0f,}
# BACKGROUND_COLOR={'透明':0x00,'暗蓝':0x10,'暗绿':0x20,'暗天蓝':0x30,'暗红':0x40,'暗粉':0x50,'暗黄':0x60,'暗白':0x70,'暗灰':0x80,'天蓝':0xb0,'蓝':0x90,'绿':0xa0,'红':0xc0,'粉':0xd0,'黄':0xe0,'白':0xf0,}
def set_cmd_text_color(name='暗白'):
	if not CTYPES_AVAILABLE:return
	ctypes.windll.kernel32.SetConsoleTextAttribute(ctypes.windll.kernel32.GetStdHandle(-11),FOREGROUND_COLOR.get(name,7))
def cprint(text,color='暗白',end='',flush=True):
	"""带颜色打印，打印后自动恢复默认色(7=暗白)"""
	sys.stdout.flush()
	set_cmd_text_color(color)
	print(text,end=end,flush=flush)
	set_cmd_text_color()
	sys.stdout.flush()
def now_time():t=datetime.datetime.today();return t.strftime('[%Y-%m-%d_%H:%M:%S.%f')[:-3]+']'
def is_valid_date(date_str):
	try:
		datetime.datetime.strptime(date_str,'%Y%m%d')
		return True
	except ValueError:
		return False
def is_valid_ip(address):
	if not isinstance(address,str):return False
	try:
		return str(ipaddress.IPv4Address(address))==address
	except(ipaddress.AddressValueError,TypeError):
		return False
def is_valid_tcp_port(port):
	return type(port)is int and 1<=port<=65535
def is_private_lan_ip(address):
	try:
		ip_obj=ipaddress.IPv4Address(address)
		return ip_obj.is_private and not(ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_unspecified or ip_obj.is_reserved)
	except ipaddress.AddressValueError:
		return False
def is_valid_mask(mask):
	try:
		mask_int=int(ipaddress.IPv4Address(mask))
	except ipaddress.AddressValueError:
		return False
	if 0==mask_int or 0xFFFFFFFF==mask_int:return True
	mask_bin=f'{mask_int:032b}'
	return '01' not in mask_bin
def is_valid_gateway_logic(ip_addr,mask,gate_way):
	try:
		ip_obj=ipaddress.IPv4Address(ip_addr)
		mask_obj=ipaddress.IPv4Address(mask)
		gate_obj=ipaddress.IPv4Address(gate_way)
		mask_int=int(mask_obj)
		ip_int=int(ip_obj)
		gate_int=int(gate_obj)
	except ipaddress.AddressValueError:
		return False
	if not is_private_lan_ip(gate_way):return False
	if not is_valid_mask(mask):return False
	if (ip_int&mask_int)!=(gate_int&mask_int):return False
	network_int=ip_int&mask_int
	broadcast_int=network_int|(~mask_int&0xFFFFFFFF)
	if gate_int in(network_int,broadcast_int):return False
	return True
def is_valid_dns_logic(dns):
	if '0.0.0.0'==dns:return True
	try:
		dns_obj=ipaddress.IPv4Address(dns)
	except ipaddress.AddressValueError:
		return False
	if dns_obj.is_unspecified or dns_obj.is_multicast or dns_obj.is_reserved:return False
	if dns_obj.is_loopback or dns_obj.is_link_local:return False
	return True
def is_same_subnet(ip1,ip2,mask):
	try:
		ip1_int=int(ipaddress.IPv4Address(ip1))
		ip2_int=int(ipaddress.IPv4Address(ip2))
		mask_int=int(ipaddress.IPv4Address(mask))
	except ipaddress.AddressValueError:
		return False
	if not is_valid_mask(mask):return False
	return (ip1_int&mask_int)==(ip2_int&mask_int)
def Bytes2HEX(B,sep='',Upper=True):
	try:
		sum(B)
	except TypeError as E:
		print("!!!错误，Bytes2HEX传入的B内包含非数字:",list(B),str(E))
		pause()
		return 0x0000
	if any([x<0 or x>255 for x in B]):
		print("!!!错误，Bytes2HEX传入的B内数字超限:",list(B))
		pause()
	return sep.join(['%02X'%i for i in B]) if Upper else sep.join(['%02x'%i for i in B])
def get_main_file_info() -> dict:
	r"""
	获取主执行文件的核心路径信息（兼容所有Windows运行场景，Python 3.6.8适配）
	场景支持：
	1. PyInstaller编译后的EXE（双击/命令行运行）
	2. 双击.py文件运行
	3. 当前目录命令行执行：文件名.py
	4. 当前目录命令行执行：python 文件名.py
	5. 任意目录命令行执行：python 完整路径/文件名.py
	返回值说明（字典）：
	- main_dir:主文件所在文件夹的绝对路径（如 C:\test）
	- main_filename:主文件名称（如 main.py / main.exe）
	- main_full_path:主文件的完整绝对路径（如 C:\test\main.py）
	异常时所有值返回空字符串
	"""
	try:
		# 1. 处理PyInstaller编译的EXE场景（优先级最高）
		if getattr(sys,'frozen',False):
			# sys.executable 指向EXE的完整路径
			main_full_path=os.path.abspath(sys.executable)
		# 2. 处理所有.py文件运行场景
		else:
			# sys.argv[0] 始终指向启动Python的主文件（即使在导入模块中调用）
			# 转为绝对路径，兼容「当前目录执行」的相对路径场景
			main_full_path=os.path.abspath(sys.argv[0])
		
		# 3. 规范路径（处理Windows路径分隔符、多余斜杠等）
		main_full_path=os.path.normpath(main_full_path)
		
		# 4. 拆分文件夹路径和文件名
		main_dir=os.path.dirname(main_full_path)+os.path.sep
		main_filename=os.path.basename(main_full_path)
		
		return {
			"main_dir":main_dir,
			"main_filename":main_filename,
			"main_full_path":main_full_path
		}
	except Exception as e:
		# 极端异常场景返回空字符串（如交互式运行）
		print(f"获取主文件路径失败：{str(e)}")
		return {
			"main_dir":"",
			"main_filename":"",
			"main_full_path":""
		}
def get_file_size(file_path:str) -> int:
	"""
	获取文件的大小（单位：字节）
	:param file_path:文件路径（支持相对/绝对路径）
	:return:文件大小（字节），文件不存在/不是文件/无访问权限时返回 0
	"""
	try:
		# 先校验路径是否为文件（排除目录）
		if not os.path.isfile(file_path):
			return 0
		# 获取文件大小（字节），os.path.getsize 直接返回文件的字节数
		file_size=os.path.getsize(file_path)
		return file_size
	except (OSError,FileNotFoundError,PermissionError):
		# 捕获常见异常：文件不存在、无访问权限、路径非法等，统一返回 0
		return 0
def get_file_md5(file_path:str,chunk_size:int=4096) -> str:
	"""
	计算文件的MD5校验值（文件唯一指纹），文件无效/读取失败时返回空字符串
	:param file_path:文件路径（支持拖入带双引号的路径）
	:param chunk_size:分块读取大小（默认4096字节，平衡效率和内存占用）
	:return:32位MD5小写字符串，失败返回空字符串
	"""
	# 校验文件合法性
	try:
		if not os.path.isfile(file_path):
			return ""
	except (OSError,PermissionError):
		return ""
	md5_obj=hashlib.md5()# 分块计算MD5（避免大文件占用过多内存）
	try:
		with open(file_path,'rb') as f:# 二进制模式读取，避免编码问题
			while True:
				chunk=f.read(chunk_size)
				if not chunk:
					break
				md5_obj.update(chunk)
		return md5_obj.hexdigest().upper()  # 返回32位大写MD5字符串
	except (FileNotFoundError,PermissionError,IOError):
		# 捕获文件不存在、无权限、读取失败等异常
		return ""
def get_Impinj_Version(file_path:str) -> str:
	"""
	根据Impinj固件文件的MD5值判定版本
	:param file_path:固件文件路径
	:return:版本字符串（如"2.2"），无匹配则返回空字符串
	"""
	return GetImpinjFileInfo(file_path)["版本"]
def _GetImpinjVersionFromFileASCII(file_path:str) -> str:
	try:
		with open(file_path,'rb') as f:
			file_bytes=f.read()
	except (FileNotFoundError,PermissionError,IOError):
		return"未知"
	if len(file_bytes)<=164:return"未知"
	try:
		ascii_bytes=file_bytes[164:].split(b'\x00',1)[0]
		ascii_text=ascii_bytes.decode('ascii',errors='ignore').strip()
	except Exception:
		return"未知"
	if ascii_text:return ascii_text
	return"未知"
def GetImpinjFileInfo(file_path:str) -> dict:
	# MD5-版本映射表，后续新增版本直接添加键值对即可
	# 示例值仅作演示，需替换为你实际的固件MD5和对应版本
	version_md5_map={
		"62D57C58D8596907D2F22151545B1B21":{"版本":"1.1.0","俗称":"1.1","字节数":190180},
		"1BB29E9A014DB07AEE7B14482923F0DD":{"版本":"2.00.00","俗称":"2.0","字节数":160804},#未公开测试版本
		"911ED8DBE5F2FB606191F16EFCC8492B":{"版本":"2.00.00-ENG4","俗称":"ENG4","字节数":160764},#未公开测试版本
		"30D6B16B1E7FE9D0A350401056584AD1":{"版本":"2.00.00-ENG5","俗称":"ENG5","字节数":160764},#未公开测试版本
		"9014607BB7C930AD1612CC9712654EDE":{"版本":"2.00.00+ENG6","俗称":"ENG6","字节数":160996},#未公开测试版本
		"366FB6C819C8D11EA0B578A2F94FD930":{"版本":"2.01.02","俗称":"2.1.2","字节数":193808},#未公开测试版本
		"65A7FE95274DC00445A57508C9D9D6AE":{"版本":"2.01.01","俗称":"2.1","字节数":192744},
		"94D2910B83469837BA4917905D6469BF":{"版本":"2.02.00","俗称":"2.2","字节数":224772},
		"07387FFE66580C96B8DE8640903C4CA9":{"版本":"2.02.02","俗称":"2.2.2","字节数":225060},
		"FF34CF3789A1CFD2925890C447827CF6":{"版本":"2.02.04+ENG1","俗称":"2.2.4+ENG1","字节数":224772}#未公开测试版本
	}
	# 获取文件MD5值
	file_md5=get_file_md5(file_path)
	# 从映射表查找版本，无匹配返回空字符串
	if file_md5 in version_md5_map:return version_md5_map[file_md5]
	return {"版本":_GetImpinjVersionFromFileASCII(file_path),"俗称":"未知","字节数":get_file_size(file_path)}
def print_all_key_values(obj,indent=0):
	prefix=" "*indent
	if isinstance(obj,dict):
		for key,value in obj.items():
			print(f"{prefix}{key}:",end='\n',flush=True)
			print_all_key_values(value,indent+1)
	elif hasattr(obj,'__dict__'):
		print(f"{prefix}{type(obj).__name__}:",end='\n',flush=True)
		for key,value in vars(obj).items():
			print(f"{prefix} {key}:",end='\n',flush=True)
			print_all_key_values(value,indent+2)
	elif isinstance(obj,(list,tuple,set)):
		print(f"{prefix}{type(obj).__name__}:",end='\n',flush=True)
		for item in obj:
			print_all_key_values(item,indent+1)
	else:
		print(f"{prefix}{obj}")
def print_all_attributes(obj):
	for attr_name in dir(obj):
		try:
			attr_value=getattr(obj,attr_name)
			print(f"{attr_name}:{attr_value}")
		except Exception as e:
			print(f"{attr_name}:无法获取值({str(e)})")
def check_zero(it,key='全零'):#全零->True
	return{"全非零":all(it),"存在非零":any(it),"存在零":not all(it),"全零":not any(it),"混杂":any(it)and not all(it)}.get(key,not any(it))
def isImpinjType(BYTES):#使用03，不能拿到SIM3800旧/SIM3900旧的:3330000，不能拿到SIM3600新的:3340000，不能拿到SIM3800新的:3350000，不能拿到SIM3900新的:3360000，不能拿到SIM3500新的:3370000
	BYTES=list(BYTES)
	# return len(BYTES)>=2 and BYTES[0]in(0x31,0x32,0x33,0x34) and BYTES[1]in(0,1,2,3,4,0x10,0x20,0x30,0x40,0x50,0x60,0x70)
	# return len(BYTES)>=1 and BYTES[0]in(0x31,0x32,0x33,0x34)
	return len(BYTES)>=2 and BYTES[0]in(0x31,0x32,0x33,0x34) and BYTES[1]in(0,1,2,3,4,0x10,0x20)
def ImpinjType(BYTES):#经过上函数判断后才能进入，03指令拿到的版本，才能进入
	BYTES=list(BYTES)
	if len(BYTES)>=4 and BYTES[1]==0 and BYTES[3]in(0x40,0x41,0x42,0x43):
		ret="SIM"+{0x31:'7',0x32:'5',0x33:'3',0x34:'9'}[BYTES[0]]+'700V'+str(BYTES[3]-0x3F)
	elif len(BYTES)>=4 and BYTES[1]==0x20 and BYTES[3]==0x40:
		ret="SIM"+{0x31:'7',0x32:'5',0x33:'3',0x34:'9'}[BYTES[0]]+'700'
	else:
		ret="SIM"+{0x31:'7',0x32:'5',0x33:'3',0x34:'9'}[BYTES[0]]
		# ret+={0:'100',1:'110',2:'200',3:'300',4:'400',0x10:'500旧',0x20:'600旧',0x30:'800/900旧',0x40:'600新',0x50:'800新',0x60:'900新',0x70:'500新'}[BYTES[1]]
		ret+={0:'100',1:'110',2:'200',3:'300',4:'400',0x10:'500旧',0x20:'600旧'}[BYTES[1]]
	return ret
def CalcCRC(msgbuf):
	try:
		sum(msgbuf)
	except TypeError as E:
		print("!!!错误，CalcCRC传入的msgbuf内包含非数字:",list(msgbuf),str(E))
		pause()
		return 0x0000
	if any([x<0 or x>255 for x in msgbuf]):
		print("!!!错误，CalcCRC传入的msgbuf内数字超限:",list(msgbuf))
		pause()
		return 0x0000
	if len(msgbuf)<3:return 0xFFFF
	calcCrc=0xFFFF
	for i in range(1,len(msgbuf)):
		for dcdBit in range(7,-1,-1):
			xorFlag=calcCrc>>15
			calcCrc=msgbuf[i]>>dcdBit&1|calcCrc<<1&0xFFFF
			if xorFlag:calcCrc^=0x1021
	return calcCrc
def CalcSubCRC(msgbuf):
	return sum(msgbuf)&0xFF
def CalcTagCRC(datas):
	crcVal=0xFFFF
	for data in datas:
		for bit in range(7,-1,-1):
			if crcVal>>15!=((data>>bit)&1):
				crcVal=((crcVal<<1)^0x1021)&0xFFFF
			else:
				crcVal=(crcVal<<1)&0xFFFF
	return crcVal^0xFFFF
def CalcHidCRC(msgbuf):
	try:
		return sum(msgbuf)&0xFFFF
	except TypeError as E:
		print("!!!错误，CalcHidCRC传入的msgbuf内包含非数字:",msgbuf,str(E))
		pause()
		return 0x0000
def IsUSB(s):
	if not HID_AVAILABLE:
		return False
	return isinstance(s,(hid.device,_HidConnection))
def IsIP(s):
	if not TCP_AVAILABLE:
		return False
	return isinstance(s,socket.socket)
def IsSerial(s):
	if not SERIAL_AVAILABLE:
		return False
	return isinstance(s,serial.Serial)

def parse_cmd_code(cmd_code):
	"""解析指令码，返回(指令类型,指令字节,错误信息)"""
	cmd_bytes=b''
	try:
		# 处理int类型
		if isinstance(cmd_code,int):
			if 0x00<=cmd_code<=0xFF:
				cmd_bytes=cmd_code.to_bytes(1,'big')
			elif 0x0000<=cmd_code<=0xFFFF:
				cmd_bytes=cmd_code.to_bytes(2,'big')
			else:
				return '','','指令码int值需为0-255（通用）或0-65535（扩展）'
		# 处理字符串类型
		elif isinstance(cmd_code,str):
			cleaned=cmd_code.replace(' ','').strip()
			if not cleaned:
				return '','','指令码字符串不能为空'
			# 去除0x/0X前缀
			if cleaned.startswith(('0x','0X')):
				cleaned=cleaned[2:]
			if not re.fullmatch(r'[0-9a-fA-F]+',cleaned):
				return '','','指令码字符串含非十六进制字符'
			# 确保长度为2或4（1字节→2位hex，2字节→4位hex）
			if len(cleaned) not in (2,4):
				return '','','指令码字符串长度需为2（通用）或4（扩展）位十六进制'
			cmd_bytes=bytes.fromhex(cleaned)
		# 处理列表类型
		elif isinstance(cmd_code,list):
			if len(cmd_code) not in (1,2):
				return '','','指令码列表长度需为1（通用）或2（扩展）'
			for b in cmd_code:
				if not isinstance(b,int)or b<0 or b>255:
					return '','','指令码列表元素需为0-255整数'
			cmd_bytes=bytes(cmd_code)
		# 处理字节类型
		elif isinstance(cmd_code,bytes):
			if len(cmd_code) not in (1,2):
				return '','','指令码字节长度需为1（通用）或2（扩展）'
			cmd_bytes=cmd_code
		else:
			return '','',f'不支持的指令码类型：{type(cmd_code).__name__}'
	except Exception as e:
		return '','',f'指令码解析失败：{str(e)}'
	# 判断指令类型
	if len(cmd_bytes)==1:
		return 'general',cmd_bytes,''
	elif len(cmd_bytes)==2:
		if cmd_bytes[0]==0xAA:
			return 'extended',cmd_bytes,''
		else:
			return '','','扩展指令码必须以AA开头（首字节0xAA）'
	else:
		return '','','指令码长度错误，仅支持1或2字节'

def parse_data(data):
	"""解析data域，返回(数据字节,错误信息)"""
	# 空数据处理
	if data is None or data==''or(isinstance(data,bytes)and len(data)==0)or(isinstance(data,list)and len(data)==0):
		return b'',''
	try:
		# 处理列表类型
		if isinstance(data,list):
			for b in data:
				if not isinstance(b,int)or b<0 or b>255:
					return b'','data列表元素需为0-255整数'
			return bytes(data),''
		# 处理字符串类型
		elif isinstance(data,str):
			# 去除所有空白字符（空格、tab、换行、回车、换页等）+ 0x/0X前缀
			cleaned=re.sub(r'\s+','',data).strip()
			if not cleaned:
				return b'',''
			if cleaned.startswith(('0x','0X')):
				cleaned=cleaned[2:]
			if not re.fullmatch(r'[0-9a-fA-F]*',cleaned):
				# print(cleaned)
				return b'','data字符串含非十六进制字符'
			return bytes.fromhex(cleaned) if cleaned else b'',''
		# 处理字节类型
		elif isinstance(data,bytes):
			return data,''
		else:
			return b'',f'不支持的data类型：{type(data).__name__}'
	except Exception as e:
		return b'',f'data解析失败：{str(e)}'

def build_command(cmd_code,data=None,P=False,sep=''):
	"""
	生成指令函数（统一返回bytes类型）
	:param cmd_code:指令码（支持int/str/list/bytes，通用1字节/扩展2字节）
	:param data:data域（支持None/str/list/bytes）
	:param P:是否打印指令（默认False）
	:param sep:打印间隔符（默认''）
	:return:生成的指令（bytes类型），错误返回b''
	"""
	# 1. 解析指令码
	cmd_type,cmd_bytes,cmd_err=parse_cmd_code(cmd_code)
	if cmd_err:
		print(f'指令生成失败：{cmd_err}')
		return b''
	
	# 2. 解析data域
	data_bytes,data_err=parse_data(data)
	if data_err:
		print(f'指令生成失败：{data_err}')
		return b''
	
	# 3. 构建指令
	try:
		if cmd_type=='general':
			# 通用指令：FF+len+cmd+data+CRC
			len_field=len(data_bytes)
			# 构建frame（用于计算CRC）
			frame=[0xFF,len_field]+list(cmd_bytes)+list(data_bytes)
			# 计算CRC
			crc=CalcCRC(frame)
			# 拼接完整指令
			command=frame+list(crc.to_bytes(2, 'big'))
			# 校验总长度（最大255字节）
			if len(command)>255:
				print(f'指令生成失败：通用指令总长度{len(command)}超过255字节限制')
				return b''
		
		else:# extended
			# 扩展指令：FF+len+AA+Moduletech+aaxx+subdata+subcrc+BB+CRC
			moduletech=b'Moduletech'  # 固定10字节
			# 计算SubCRC（aaxx+subdata）
			sub_data_for_crc=cmd_bytes+data_bytes
			subcrc=CalcSubCRC(sub_data_for_crc)
			# 构建扩展体（Moduletech+aaxx+subdata+subcrc+BB）
			extended_body=list(moduletech)+list(cmd_bytes)+list(data_bytes)+[subcrc,0xBB]
			len_field=len(extended_body)
			# 构建frame（用于计算CRC）
			frame=[0xFF,len_field,0xaa]+extended_body
			# 计算CRC
			crc=CalcCRC(frame)
			# 拼接完整指令
			command=frame+list(crc.to_bytes(2, 'big'))
			# 校验总长度（最大255字节）
			if len(command)>255:
				print(f'指令生成失败：扩展指令总长度{len(command)}超过255字节限制')
				return b''
		
		# 4. 统一返回bytes类型
		result=bytes(command)
		
		# 5. 打印指令（如果P=True）
		if P:print(f'构建指令：{Bytes2HEX(result,sep=sep)}')
		
		return result
	
	except Exception as e:
		print(f'指令生成失败：未知错误 - {str(e)}')
		return b''
	# finally:
		# pass
"""
# 测试带0x前缀的扩展指令码：0xaa40（不同data类型均返回bytes）
print("===测试'0xaa40'指令码===")
res1=build_command('0xaa40',data='b1 01	02',P=True,sep=' ')
print(f'返回值：{Bytes2HEX(res1)}')

# 测试int类型指令码+bytes类型data
res2=build_command(0xAA60,data=bytes.fromhex('0001 02960101 02960200 019706 13AA4D6F64756C6574656368AA48001600800088bb'),P=False)
print(f'返回值：{Bytes2HEX(res2)}')

# 测试列表类型指令码+列表类型data
res3=build_command([0xAA,0x4D],data=[0x00,0x01,0x00,0x0D,0xC6,0x5E,0x0C,0xE4],P=True,sep='')
print(f'返回值：{Bytes2HEX(res3)}')

# 测试通用指令（空data）
res4=build_command('0x03',data='',P=True,sep=' ')
print(f'返回值：{Bytes2HEX(res4)}')

# 测试通用指令（启用天线1+3）
res5=build_command(0x91,data='0201010303',P=True,sep=' ')
print(f'返回值：{Bytes2HEX(res5)}')

# 测试通用指令（rfmode双字节205）
res5=build_command(0x9b,data='050200cd',P=True,sep='')
print(f'返回值：{Bytes2HEX(res5)}')

# 测试错误情况（返回空bytes）
res7=build_command('AB40',data='	 01 02	',P=True)
print(f'返回值：{Bytes2HEX(res7)}')
# """
def GetConnectionName(s):
	if IsSerial(s):
		try:
			# print('-'*32)
			# print_all_attributes(s)
			# print('-'*32)
			# print_all_key_values(s)
			# print('-'*32)
			return f"{s.name}:{s.baudrate}"
		except Exception as e:
			print(f"获取串口名称时出错:{e}")
			return "未知串口名称"
	elif IsIP(s):
		try:
			return f"{s.getsockname()[0]}:{s.getsockname()[1]}<--->{s.getpeername()[0]}:{s.getpeername()[1]}"
		except Exception as e:
			print(f"获取 IP 连接信息时出错:{e}")
			return "未知 IP 连接信息"
	elif IsUSB(s):
		return"USB"
	else:
		return "未知连接类型"
def ListPorts():
	if not SERIAL_AVAILABLE:
		return []
	try:
		ports=[]
		for x in list_ports.comports():
			# port_info=' '.join(str(getattr(x,k,'')) for k in('device','description','hwid','manufacturer','name')).lower()
			# if any(k in port_info for k in('bluetooth','bth','蓝牙')):continue
			if x.device and not(IS_MACOS and(x.device.endswith('Bluetooth-Incoming-Port')or x.device.endswith('debug-console'))):ports.append(x.device)
		return sorted(ports,key=lambda x:(len(x),x),reverse=True)
	except Exception as E:
		print('ListPorts未知异常',str(E))
		return []
	# return sorted([x.device for x in list_ports.comports() if x.device],key=lambda x:(len(x),x),reverse=True)
	r"""
	serial.tools.list_ports可能有如下错误
	Traceback (most recent call last):
	  File "C:\Program Files\Python36\ModuleAPI.py",line 873,in<module>
		rdr=Create(input("请输入读写器地址:"))
	  File "C:\Program Files\Python36\ModuleAPI.py",line 764,in Create
		return FindAllSerialAndTCPAndHid()
	  File "C:\Program Files\Python36\ModuleAPI.py",line 608,in FindAllSerialAndTCPAndHid
		ports=ListPorts()
	  File "C:\Program Files\Python36\ModuleAPI.py",line 117,in ListPorts
		return sorted([x.device for x in serial.tools.list_ports.comports()],key=lambda x:(len(x),x),reverse=True)
	  File "C:\Program Files\Python36\Lib\site-packages\serial\tools\list_ports_windows.py",line 412,in comports
		return list(iterate_comports())
	  File "C:\Program Files\Python36\Lib\site-packages\serial\tools\list_ports_windows.py",line 334,in iterate_comports
		info.serial_number=get_parent_serial_number(devinfo.DevInst,info.vid,info.pid)
	  File "C:\Program Files\Python36\Lib\site-packages\serial\tools\list_ports_windows.py",line 197,in get_parent_serial_number
		vid=int(m.group(1),16)
	AttributeError: 'NoneType' object has no attribute 'group'
	"""
def reg_serial():
	if not WINREG_AVAILABLE:
		return []
	ret_ports=[]
	try:
		key=winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r"Hardware\DeviceMap\SerialComm")
		key_index=0
		while True:
			content=winreg.EnumValue(key,key_index)
			ret_ports.append(content[1])
			key_index+=1
	except Exception as E:
		if'key'in dir():
			winreg.CloseKey(key)
		if getattr(E,'winerror',None)!=259:print('reg_serial未知异常',str(E))
	# print(f"串口数量为{key_index},ret_ports="+Bytes2HEX(ret_ports,sep=','))
	return sorted([x for x in ret_ports if x],key=lambda x:(len(x),x),reverse=True)
def ListLinuxPorts():
	if not SERIAL_AVAILABLE or not IS_LINUX:return []
	ports=[]
	try:
		for device_name in os.listdir('/dev'):
			if re.match(r'tty(S|USB|ACM|AMA|FIQ|THS)\d+$',device_name):ports.append('/dev/'+device_name)
	except Exception as E:
		print('ListLinuxPorts未知异常',str(E))
		return []
	return sorted(ports,key=lambda x:(len(x),x),reverse=True)
def GetSerialPorts():
	ports=ListPorts()
	if IS_LINUX:ports=sorted(set(ports+ListLinuxPorts()),key=lambda x:(len(x),x),reverse=True)
	if not ports and IS_WINDOWS:ports=reg_serial()
	return ports
def GenHidCommand(msgbuf)->list:
	retlist=[]
	msgbuf=list(msgbuf)
	while msgbuf:
		currentcommand=[0]
		L=len(msgbuf)
		if L<=61:
			currentcommand.append(len(msgbuf))
			currentcommand.extend(msgbuf)
			HidCRC=CalcHidCRC(msgbuf)
			currentcommand.extend(HidCRC.to_bytes(2, 'big'))
			del(msgbuf[:L])
		else:
			currentcommand.append(61)
			currentcommand.extend(msgbuf[:61])
			HidCRC=CalcHidCRC(msgbuf[:61])
			currentcommand.extend(HidCRC.to_bytes(2, 'big'))
			del(msgbuf[:61])
		# print("HID_SEND:"+Bytes2HEX(currentcommand,sep=''))
		retlist.append(currentcommand)
	return retlist
def _prepare_hid_write_frame(frame):
	return frame+[0]*(65-len(frame)) if IS_MACOS and len(frame)<65 else frame
def DataTransport(s,Data):
	if sum([0<=i<=255 for i in Data])!=len(Data):
		print("DataTransport中的Data含有非法元素",Bytes2HEX(Data,sep=''))
		return -1
	payload=bytes(Data)
	if IsSerial(s):
		try:
			if not s.isOpen():return -1
		except Exception:
			return -1
		try:
			result=0
			while result<len(payload):
				written=s.write(payload[result:])
				if type(written)is not int or written<=0 or written>len(payload)-result:
					print(f"DataTransport IsSerial(s) s.write(bytes(Data))返回非法长度:{written}")
					return -1
				result+=written
		except Exception as e:
			print(f"DataTransport IsSerial(s) s.write(bytes(Data))错误:{e}")
			# pause()
			return -1
	elif IsIP(s):
		try:
			s.sendall(payload)###主动模式会在这里闪退
			result=len(payload)
		except Exception as e:
			print(f"DataTransport IsIP(s) s.sendall(bytes(Data))错误:{e}")
			# pause()
			return -1
	elif IsUSB(s):
		sendlist=GenHidCommand(Data)
		for _ in sendlist:
			_= _prepare_hid_write_frame(_)
			try:
				ret=s.write(_)#程序会自动补全65字节(后面全填0):_+=[0]*(65-len(_))
				# print('write:'+Bytes2HEX(_,sep=''))
				# print("ret:",ret)
			except Exception as e:
				print(f"DataTransport IsUSB(s) s.write(_)错误:{e}")
				return -1
			if ret!=65:
				print(f"DataTransport IsUSB(s) s.write(_)返回{ret},期望65")
				return -1
		result=0
	else:
		print("DataTransport中的s不是IP/串口/USB，无法发送数据",s)
		pause()
		result=-1
	return result
def gettimeout(s):
	if IsSerial(s):
		try:
			return s.timeout
		except Exception as e:
			print(f"获取串口超时时间时出错:{e}")
			return -1
	elif IsIP(s):
		try:
			return s.gettimeout()
		except Exception as e:
			print(f"获取 IP 超时时间时出错:{e}")
			return -1
	elif IsUSB(s):
		return _get_hid_state(s)['timeout']
	else:
		print("gettimeout中的s不是IP/串口/USB",s)
		return -1
def settimeout(s,timeout):
	if IsSerial(s):
		try:
			if not s.isOpen():return -1
			s.timeout=timeout
			return s.timeout
		except Exception as e:
			print(f"设置串口超时时间时出错:{e}")
			return -1
	elif IsIP(s):
		try:
			return s.settimeout(timeout)
		except Exception as e:
			print(f"设置IP超时时间时出错:{e}")
			return -1
	elif IsUSB(s):
		state=_get_hid_state(s)
		with state['lock']:
			state['timeout']=timeout
		return state['timeout']
	else:
		print("settimeout中的s不是IP/串口/USB",s)
		return -1
# def UnpackCommand(realcommand:list):
# 	ret=[]
# 	# print(f'UnpackCommand:'+Bytes2HEX(realcommand))
# 	while realcommand:
# 		CurrnetCommand=realcommand[:realcommand[1]+7]
# 		CRC16=CalcCRC(CurrnetCommand[:-2])
# 		# print(f'CRC16:{CRC16:0>4X}')
# 		if CRC16!=(CurrnetCommand[-2]<<8)|CurrnetCommand[-1]:
# 			print('Unpack CRC_ERR:'+Bytes2HEX(realcommand,sep=''))
# 			return b''
# 		del(realcommand[:realcommand[1]+7])
# 		ret.append(bytes(CurrnetCommand))
# 	return ret
def _DataReceiveAllHid(s):
	state=_get_hid_state(s)
	with state['lock']:
		# 先尝试读取HID缓冲区，成功后再清空剩余缓存
		buffer=state['buffer']
		for __ in range(5):
			try:
				R=s.read(64,1)#单位ms
			except Exception as e:#没收到
				print('DataReceiveAll 没收到',str(e))
				state['buffer']=buffer
				return b''
			if R==[]:
				break
			if len(R)>=3:
				hid_data_len=R[0]
				if len(R)>=hid_data_len+3:
					hid_data=R[1:1+hid_data_len]
					hid_crc=int.from_bytes(R[1+hid_data_len:1+hid_data_len+2],'big')
					if CalcHidCRC(hid_data)==hid_crc:
						buffer+=bytes(hid_data)
		state['buffer']=b''
		return buffer

def DataReceiveAll(s):#立即返回所有缓冲区的数据，无需等待超时
	if IsSerial(s):
		try:
			if not s.isOpen():return b''
		except Exception:
			return b''
		lasttimeout=gettimeout(s)
		if lasttimeout==-1:return b''
		if settimeout(s,0)==-1:return b''
		try:
			buffer=s.readall()
		except Exception as E:
			print(f'连接异常',str(E))
			settimeout(s,lasttimeout)
			return b''
		# print(f"COM已清空缓冲区，共丢弃{len(buffer)}字节数据"+Bytes2HEX(buffer))
		settimeout(s,lasttimeout)
		return buffer
	elif IsIP(s):
		"""
		try:
			return s.recv(1024)
		except Exception as e:#没收到
			# print("没收到",e)
			return b''
		"""
		buffer=b""
		try:
			original_timeout=s.gettimeout()#保存原始超时设置
			# 设置非阻塞模式（避免在无数据时阻塞）
			s.setblocking(False)
		except Exception as E:
			print(f'连接异常',str(E),Bytes2HEX(buffer,sep=''))
			return b''
		try:
			while True:
				try:
					# 每次读取1024字节
					data=s.recv(1024)
					if not data: # 连接关闭时返回空字节串
						break
					buffer+=data
				except BlockingIOError:
					# 缓冲区已无数据，退出循环
					break
				except Exception as E:
					print(f'连接异常',str(E),Bytes2HEX(buffer,sep=''))
					return b''
			# print(f"socket已清空缓冲区，共丢弃{len(buffer)}字节数据"+Bytes2HEX(buffer))
		finally:
			try:
				s.setblocking(True)#恢复阻塞模式
				s.settimeout(original_timeout)#恢复原始超时
			except Exception:
				pass
		return buffer  # 可选：返回被清空的数据
	elif IsUSB(s):
		return _DataReceiveAllHid(s)
	else:
		print("DataReceiveAll中的s不是IP/串口/USB",s)
		return b''
def IsCompleteCommand(rmsg):
	msg=rmsg[:]
	# print('msg:'+Bytes2HEX(msg,sep=''))
	while msg:
		if len(msg)<7:
			# print('IsCompleteCommand len(msg)<7'+Bytes2HEX(msg,sep=''))
			return False
		if msg[0]!=0xff:
			print('IsCompleteCommand msg[0]!=0xff'+Bytes2HEX(msg,sep=''))
			return False
		if msg[1]+7>len(msg):
			# print('IsCompleteCommand msg[1]+7>len(msg)'+Bytes2HEX(msg,sep=''))
			return False
		del(msg[:msg[1]+7])
	# print('return True')
	return True

def _read_serial_exact(s,size,deadline,retry_on_empty=True):
	"""在同一个总截止时间内读取串口数据；缓冲区不足时临时设置并恢复 timeout。"""
	if size<=0:return b''
	buffer=b''
	try:
		original_timeout=s.timeout
	except Exception:
		return buffer
	active_timeout=original_timeout
	timeout_changed=False
	idle_timeout=0.05
	if (type(original_timeout)in(int,float)
		and original_timeout>idle_timeout):
		idle_timeout=original_timeout
	idle_deadline=min(deadline,time.perf_counter()+idle_timeout)
	try:
		while len(buffer)<size:
			now=time.perf_counter()
			remaining=min(deadline-now,idle_deadline-now)
			if remaining<=0:break
			try:
				available=s.in_waiting
			except Exception:
				try:available=s.inWaiting()
				except Exception as e:
					print(f"DataReceive IsSerial(s)获取待读取字节数错误:{e}")
					break
			read_size=min(size-len(buffer),available)if available>0 else size-len(buffer)
			if available<=0 and not timeout_changed:
				read_timeout=remaining
				if (type(original_timeout)in(int,float)
					and original_timeout>=0):
					read_timeout=min(original_timeout,remaining)
				if read_timeout!=original_timeout:
					timeout_changed=True
					try:
						s.timeout=read_timeout
						active_timeout=read_timeout
					except Exception as e:
						print(f"DataReceive IsSerial(s)设置剩余超时错误:{e}")
						break
			try:chunk=s.read(read_size)
			except Exception as e:
				print(f"DataReceive IsSerial(s) s.read(...)错误:{e}")
				break
			if chunk:
				buffer+=chunk
				idle_deadline=min(deadline,time.perf_counter()+idle_timeout)
			elif not retry_on_empty:break
			if len(buffer)<size and timeout_changed and active_timeout!=0:
				try:
					s.timeout=0
					active_timeout=0
				except Exception as e:
					print(f"DataReceive IsSerial(s)设置非阻塞超时错误:{e}")
					break
			if not chunk:
				sleep_remaining=min(deadline-time.perf_counter(),idle_deadline-time.perf_counter())
				if sleep_remaining>0:
					# Windows上1ms休眠可能按系统时钟粒度放大，使用更短间隔控制截止时间
					time.sleep(0 if sleep_remaining<=0.02 else min(0.0001,sleep_remaining))
		return buffer
	finally:
		if timeout_changed:
			try:s.timeout=original_timeout
			except Exception:pass

def _recv_tcp_exact(s,size,deadline):
	"""在同一个总截止时间内接收指定长度；EOF、超时或异常均返回空字节串。"""
	if size<0:return b''
	if size==0:return b''
	buffer=b''
	try:
		original_timeout=s.gettimeout()
	except Exception:
		return b''
	try:
		while len(buffer)<size:
			remaining=deadline-time.perf_counter()
			if remaining<=0:return b''
			try:s.settimeout(remaining)
			except Exception:return b''
			try:chunk=s.recv(size-len(buffer))
			except Exception:return b''
			if not chunk:return b''
			buffer+=chunk
		return buffer
	finally:
		try:s.settimeout(original_timeout)
		except Exception:pass

def _DataReceiveHid(s,R=0):
	state=_get_hid_state(s)
	with state['lock']:
		USBRemainingBuffer=state['buffer']
		HidTimeout=state['timeout']
		start_time=time.perf_counter()
		dirty_count=0
		try:
			# 先尝试从剩余缓存中提取完整命令
			while USBRemainingBuffer:
				if len(USBRemainingBuffer)<7:
					break
				if USBRemainingBuffer[0]!=0xFF:
					print('Head_ERR(缓存):'+Bytes2HEX(USBRemainingBuffer[:1],sep=''))
					USBRemainingBuffer=USBRemainingBuffer[1:]
					dirty_count+=1
					if dirty_count>=3:
						print(f"USB清缓冲丢弃{len(USBRemainingBuffer)}字节:"+Bytes2HEX(USBRemainingBuffer))
						USBRemainingBuffer=b''
						return b''
					continue
				cmd_len=USBRemainingBuffer[1]
				if len(USBRemainingBuffer)>=cmd_len+7:
					cmd=USBRemainingBuffer[:cmd_len+7]
					USBRemainingBuffer=USBRemainingBuffer[cmd_len+7:]
					CRC16=CalcCRC(cmd[:-2])
					if CRC16==int.from_bytes(cmd[-2:],'big'):
						return cmd
					print('CRC_ERR(缓存):'+Bytes2HEX(cmd,sep=''))
					# 保留原有 API-004 行为：候选帧已消费后，再删除新缓存首字节。
					USBRemainingBuffer=USBRemainingBuffer[1:]
					continue
				break

			# 从 HID 读取新数据
			while True:
				try:
					R=s.read(64,int(HidTimeout*1000))
				except Exception as e:
					print('DataReceive USB断开连接',str(e))
					return b''

				if R==[]:
					if USBRemainingBuffer and len(USBRemainingBuffer)>=7 and USBRemainingBuffer[0]==0xFF:
						cmd_len=USBRemainingBuffer[1]
						if len(USBRemainingBuffer)>=cmd_len+7:
							cmd=USBRemainingBuffer[:cmd_len+7]
							USBRemainingBuffer=USBRemainingBuffer[cmd_len+7:]
							CRC16=CalcCRC(cmd[:-2])
							if CRC16==int.from_bytes(cmd[-2:],'big'):
								return cmd
					return b''

				# HID 报告结构：[数据长度, 数据..., HID CRC]
				if len(R)<3:
					continue
				hid_data_len=R[0]
				if len(R)<hid_data_len+3:
					continue
				hid_data=R[1:1+hid_data_len]
				hid_crc=int.from_bytes(R[1+hid_data_len:1+hid_data_len+2],'big')
				if CalcHidCRC(hid_data)!=hid_crc:
					print('HidCRC_ERR:'+Bytes2HEX(hid_data,sep=''))
					continue

				USBRemainingBuffer+=bytes(hid_data)
				while USBRemainingBuffer:
					if len(USBRemainingBuffer)<7:
						break
					if USBRemainingBuffer[0]!=0xFF:
						print(f'Head_ERR{R}:'+Bytes2HEX(USBRemainingBuffer[:1],sep=''))
						USBRemainingBuffer=USBRemainingBuffer[1:]
						dirty_count+=1
						if dirty_count>=3:
							print(f"USB清缓冲丢弃{len(USBRemainingBuffer)}字节:"+Bytes2HEX(USBRemainingBuffer))
							USBRemainingBuffer=b''
							return b''
						continue
					cmd_len=USBRemainingBuffer[1]
					if len(USBRemainingBuffer)>=cmd_len+7:
						cmd=USBRemainingBuffer[:cmd_len+7]
						USBRemainingBuffer=USBRemainingBuffer[cmd_len+7:]
						CRC16=CalcCRC(cmd[:-2])
						if CRC16==int.from_bytes(cmd[-2:],'big'):
							return cmd
						print('CRC_ERR:'+Bytes2HEX(cmd,sep=''))
						# 保留原有 API-004 行为，见上方同类分支。
						USBRemainingBuffer=USBRemainingBuffer[1:]
						continue
					break

				if time.perf_counter()-start_time>HidTimeout:
					return b''
		finally:
			state['buffer']=USBRemainingBuffer

def DataReceive(s,R=0,deadline=None):
	# global is_interrupt
	# print(f"now_time={now_time()}DataReceive 开始")
	if IsSerial(s):
		try:
			if not s.isOpen():return b''
		except Exception:
			return b''
		try:
			# print(f"before now_time={now_time()}DataReceive IsSerial(s) s.read(1)")
			if type(deadline)in(int,float):
				ret=_read_serial_exact(s,1,deadline,retry_on_empty=False)
			else:
				ret=s.read(1)#使用之前指定的timeout的时间去等待
			# print(f"after now_time={now_time()}DataReceive IsSerial(s) s.read(1)返回{ret}")
		# except KeyboardInterrupt:
		# 	is_interrupt=True
		# 	pass
			# print(f"after now_time={now_time()}DataReceive IsSerial(s) s.read(1)中断")
			# raise  # 重新抛出KeyboardInterrupt，让上层处理
		except Exception as e:
			print(f"DataReceive IsSerial(s) s.read(1)错误:{e}")
			# pause()
			return b''
		start_DataReceive_time=time.perf_counter()
		# print(f"after start_DataReceive_time={start_DataReceive_time}")
		if not ret:#没收到
			# print('DataReceive 没收到')
			return b''
		if ret[0]!=0xFF:#脏数据，再给2次机会(最多容许3个脏数据)
			print(f'Head_ERR{R}:'+Bytes2HEX(ret,sep=''),end='')
			# s.flushOutput()
			# s.flushInput()
			buffer=DataReceiveAll(s)
			print(f"COM清缓冲丢弃{len(buffer)}字节:"+Bytes2HEX(buffer))
			if R>=2:return b''
			else:return DataReceive(s,R=R+1,deadline=deadline)
		# s_timeout=gettimeout(s)
		# print(f"s_timeout:{gettimeout(s)}")
		# settimeout(s,0.01)#单条指令，后面的数据必须在10ms内收完
		frame_deadline=start_DataReceive_time+0.5
		if type(deadline)in(int,float):
			frame_deadline=min(frame_deadline,deadline)
		ret+=_read_serial_exact(s,1,frame_deadline,retry_on_empty=False)
		if len(ret)<2:return b''
		try:
			total_cmd=ret[1]
		except Exception as E:
			print(f'出现错误',str(E),Bytes2HEX(ret,sep=''))
			return b''
		remaining_length=total_cmd+7-len(ret)
		if remaining_length>0:
			ret+=_read_serial_exact(s,remaining_length,frame_deadline)
		if total_cmd+7!=len(ret):
			print(f'{(time.perf_counter()-start_DataReceive_time)*1000:.3f}ms接收长度错误:'+Bytes2HEX(ret,sep=''))
			return b''
		CRC16=CalcCRC(ret[:-2])
		if CRC16==int.from_bytes(ret[-2:],'big'):
			# print(f'return {Bytes2HEX(ret,sep="")}')
			return ret
		else:
			print('CRC_ERR:'+Bytes2HEX(ret,sep=''))
			return b''
	elif IsIP(s):
		try:
			ret=s.recv(1)#使用之前指定的timeout的时间去等待
		except Exception as e:#没收到
			return b''
		if not ret:#EOF
			return b''
		if ret[0]!=0xFF:#脏数据，再给2次机会(最多容许3个脏数据)
			print(f'Head_ERR{R}:'+Bytes2HEX(ret,sep=''),end='')
			buffer=DataReceiveAll(s)
			print(f"TCP清缓冲丢弃{len(buffer)}字节:"+Bytes2HEX(buffer))
			if R>=2:return b''
			else:return DataReceive(s,R=R+1,deadline=deadline)
		try:
			frame_timeout=s.gettimeout()
		except Exception:
			return b''
		if type(frame_timeout)not in(int,float)or frame_timeout<=0:
			frame_timeout=0.6
		frame_deadline=time.perf_counter()+frame_timeout
		if type(deadline)in(int,float):
			frame_deadline=min(frame_deadline,deadline)
		second_byte=_recv_tcp_exact(s,1,frame_deadline)
		if not second_byte:return b''
		ret+=second_byte
		total_cmd=ret[1]
		remaining_length=total_cmd+7-len(ret)
		if remaining_length:
			remaining_data=_recv_tcp_exact(s,remaining_length,frame_deadline)
			if not remaining_data:return b''
			ret+=remaining_data
		CRC16=CalcCRC(ret[:-2])
		if CRC16==int.from_bytes(ret[-2:],'big'):
			return ret
		else:
			print('CRC_ERR:'+Bytes2HEX(ret,sep=''))
			return b''
	elif IsUSB(s):
		return _DataReceiveHid(s,R=R)
	else:
		print("DataReceive中的s不是IP/串口/USB",s)
		return b''
""""""
def SwitchToBOOTLayer(rdr,PreparingUpgrade=True,P=True):
	LayerFirst=GetLayer(rdr,P=False)
	if LayerFirst==0x12:
		HardwareVersion=GetHardwareVersion(rdr,P=False)
		ISSQM5800=HardwareVersion[:3]in(b'\xC0\x00\x00',b'\x00\x00\x00')
		if P and ISSQM5800:print(f'HardwareVersion={Bytes2HEX(HardwareVersion)}为SQM5800进BOOT后需要等3秒')
		if PreparingUpgrade:
			# 准备升级0xAB
			DataTransport(rdr,build_command(0xAA40, [0xAB, 0x01]))
			read_msg=DataReceive(rdr)#FF 0E AA 00 00 4D 6F 64 75 6C 65 74 65 63 68 AA 40 AB 01 6E 5F 
			if len(read_msg)>=7 and check_zero(read_msg[3:5]):pass
			else:print('Error准备升级 read_msg:'+Bytes2HEX(read_msg,sep=''))#;pause()
			# if P:print('Successful'if len(read_msg)>=7 and check_zero(read_msg[3:5]) else'Error',end='',flush=True)
			# if P:print('准备升级 read_msg:'+Bytes2HEX(read_msg,sep=''))
		#切换到BOOT 0x09
		# print(f'time={now_time()}before DataTransport')
		Before_Transport_time=time.perf_counter()
		DataTransport(rdr,build_command(0x09))
		# print(f'time={now_time()}after DataTransport')
		read_msg=DataReceive(rdr)
		# print(f'time={now_time()}after DataReceive')
		if P:print('Successful'if len(read_msg)>=7 and check_zero(read_msg[3:5]) else'Error',end='',flush=True)
		if P:print('切换到BOOT回应%.3fms read_msg:'%((time.perf_counter()-Before_Transport_time)*1000)+Bytes2HEX(read_msg,sep=''))
		# print(f'time={now_time()}before 等待250ms')
		# 等待250ms
		if ISSQM5800:
			time.sleep(3)
		else:
			time.sleep(0.25)
		# print(f'time={now_time()}before DataReceiveAll')
		buffer=DataReceiveAll(rdr)
		# print(f'time={now_time()}after DataReceiveAll')
		if buffer:print(f"清缓冲丢弃{len(buffer)}字节:"+Bytes2HEX(buffer))
		#由于切换到BOOT是单片机复位，单片机的Tx可能会有时序，所以可能会有脏数据00，所以此处等待后需要清空缓冲区，
		#再判定在那一层
		Layer=GetLayer(rdr,P=False)
		if Layer==0x11:
			if P:print('当前在BOOT,GetLayer==0x%02X'%Layer)
		else:
			print('当前不在BOOT,GetLayer==0x%02X'%Layer)
			# pause()
		return Layer
	elif LayerFirst==0x11:
		pass
		if P:print("当前已经是BOOT层")
	else:
		print("SwitchToBOOTLayer:获取运行在哪一层错误0x%X"%LayerFirst)
		# pause()
		# exit(0)
	return LayerFirst
def SwitchToAPPLayer(rdr,timeout=2.5,P=True):
	LayerFirst=GetLayer(rdr,P=False)
	if LayerFirst==0x11:
		lasttimeout=gettimeout(rdr)
		settimeout(rdr,timeout)#常规210ms即可。某些情况下，切APP需要耗费2.2s。考虑到网络因素，某些时候需要设置5s。
		Before_Transport_time=time.perf_counter()
		DataTransport(rdr,build_command(0x04))
		read_msg=DataReceive(rdr)
		settimeout(rdr,lasttimeout)
		if P:print('Successful'if len(read_msg)>=7 and check_zero(read_msg[3:5]) else'Error',end='',flush=True)
		if P:print('切换到APP回应%.3fms read_msg:'%((time.perf_counter()-Before_Transport_time)*1000)+Bytes2HEX(read_msg,sep=''))
		Layer=GetLayer(rdr,P=False)
		if Layer==0x12:
			if P:print('当前在APP,GetLayer==0x%02X'%Layer)
		else:
			print('当前不在APP,GetLayer==0x%02X'%Layer)
			pause()
		return Layer
	elif LayerFirst==0x12:
		if P:print("当前已经是APP层")
	else:
		print("SwitchToAPPLayer:获取运行在哪一层错误0x%X"%LayerFirst)
		# pause()
		# exit(0)
	return LayerFirst
def _GetVersionRawInfo(rdr,P=True):
	layer=GetLayer(rdr,P=False)
	layer='APP层'if layer==0x12 else'BOOT层'if layer==0x11 else'错误'
	success=False
	Hardware_index=9
	read_msg=b''
	#②不管在哪一层先尝试05指令
	DataTransport(rdr,build_command(0x05))
	read_msg=DataReceive(rdr)
	if len(read_msg)==0x54+7 and read_msg[2]==5 and check_zero(read_msg[3:5]):
		#05成功
		if P:print(f'Successful在{layer}获取05版本 read_msg:'+Bytes2HEX(read_msg,sep=''))
		if len(read_msg)==0x54+7 and read_msg[12]==0x80:#80模块
			Hardware_index+=4*4
		if P:print('Bootloader    Ver:'+Bytes2HEX(read_msg[5:5+4],sep=' '))
		if P:print('Hardware      Ver:'+Bytes2HEX(read_msg[Hardware_index:Hardware_index+4],sep=' '))
		if P:print('Firmware     Date:'+Bytes2HEX(read_msg[13:13+4],sep=' '))
		if P:print('Firmware      Ver:'+Bytes2HEX(read_msg[17:17+4],sep=' '))
		if P:print('Supported Protool:'+Bytes2HEX(read_msg[21:21+4],sep=' '))
		success=True
	else:
		#05失败，使用03
		if P:print(f'Error在{layer}获取05版本(不支持) read_msg:'+Bytes2HEX(read_msg,sep=''))
		DataTransport(rdr,build_command(0x03))
		read_msg=DataReceive(rdr)
		if P:print(('Successful'if len(read_msg)>=7 and read_msg[2]==3 and check_zero(read_msg[3:5]) else'Error')+f'在{layer}获取03版本 read_msg:'+Bytes2HEX(read_msg,sep=''))
		if len(read_msg)>=7 and read_msg[2]==3 and check_zero(read_msg[3:5]):
			Hardware_index=9 #固定Index
			if P:print('Bootloader    Ver:'+Bytes2HEX(read_msg[5:5+4],sep=' '))
			if P:print('Hardware      Ver:'+Bytes2HEX(read_msg[Hardware_index:Hardware_index+4],sep=' '))
			if P:print('Firmware     Date:'+Bytes2HEX(read_msg[13:13+4],sep=' '))
			if P:print('Firmware      Ver:'+Bytes2HEX(read_msg[17:17+4],sep=' '))
			if P:print('Supported Protool:'+Bytes2HEX(read_msg[21:21+4],sep=' '))
			success=True
	return success,layer,read_msg,Hardware_index

def GetFirmwareVersion(rdr,P=True):
	success,layer,read_msg,Hardware_index=_GetVersionRawInfo(rdr,P=P)
	if success:
		return read_msg[17:17+4]
	else:
		return b''
def GetFirmwareDate(rdr,P=True):
	success,layer,read_msg,Hardware_index=_GetVersionRawInfo(rdr,P=P)
	if success:
		return read_msg[13:13+4]
	else:
		return b''
def GetHardwareVersion(rdr,P=True):
	success,layer,read_msg,Hardware_index=_GetVersionRawInfo(rdr,P=P)
	if success:
		HardwareVerNumber=read_msg[Hardware_index:Hardware_index+4]
		return HardwareVerNumber
	else:
		return b''
def GetModuleName(rdr,P=True):
	success,layer,read_msg,Hardware_index=_GetVersionRawInfo(rdr,P=P)
	if success:
		HardwareVerNumber=read_msg[Hardware_index:Hardware_index+4]
		if not HardwareVerNumber:
			print(f'GetModuleName错误:在{layer}获取版本 read_msg:'+Bytes2HEX(read_msg,sep=''))
			return'ERROR'
		# print("!!!!!!!!!!!!!!!!!!!!!!!!!",layer,len(read_msg),hex(read_msg[12]),Bytes2HEX(read_msg[57:57+8]))
		if HardwareVerNumber in ModuleHardwareType:#查表
			ModuleName=ModuleHardwareType[HardwareVerNumber]
			# if HardwareVerNumber[3]:ModuleName+=',%02X'%HardwareVerNumber[3]
		elif (read_msg[12]!=0x80 or read_msg[2]==3)and isImpinjType(HardwareVerNumber):
			#(旧模块)需要解析(无论是否支持05)，或者(新模块)当前不支持05指令
			ModuleName=ImpinjType(HardwareVerNumber)
			if HardwareVerNumber[2]:#认证区域
				if HardwareVerNumber[2]in CertificationRegionCodes:ModuleName+=','+CertificationRegionCodes[HardwareVerNumber[2]]
				else:ModuleName+=',%02X'%HardwareVerNumber[2]
			if HardwareVerNumber[3]:
				if HardwareVerNumber[3]==0x20:
					ModuleName+='无委'#900M通道贴了SRRC滤波器
				elif (HardwareVerNumber[3]&0x20)==0x20:
					ModuleName+='无委,%02X'%HardwareVerNumber[3]
				elif HardwareVerNumber[3]==0x30:
					ModuleName+='无委+日本'#900M通道贴了SRRC滤波器，全频段贴日本滤波器
				elif (HardwareVerNumber[3]&0x30)==0x30:
					ModuleName+='无委+日本,%02X'%HardwareVerNumber[3]
				elif HardwareVerNumber[3]in(0x40,0x41,0x42,0x43):
					pass
					# ModuleName+='SIMx700外观/天线一体(陶瓷体45*45/整体50*50)'#没有软件策略
				elif (HardwareVerNumber[3]&0x40)==0x40:
					ModuleName+='SIMx700外观/天线一体(新型号未知)'#没有软件策略
				else:
					ModuleName+=',%02X'%HardwareVerNumber[3]
		elif read_msg[12]==0x80 and read_msg[2]==5 and len(read_msg)==0x54+7 and any(read_msg[57:57+8]):
			#0001以80结尾，并且05指令拿到的，并且ASCII区域有值
			#当前SQM5800存储区都是0，所以无法进入any分支，20250916通过ModuleHardwareType添加b'\xC0\x00\x00\x01':"SQM5800"临时解决
			#针对SQM5800后续要进入这个any(read_msg[57:57+8])取出型号
			ModuleName=read_msg[57:57+24].decode(errors='replace',encoding='utf-8').rstrip('\x00')#去掉结尾NUL终止符，保留0x20空格
			if HardwareVerNumber[2]:#认证区域
				if HardwareVerNumber[2]in CertificationRegionCodes:ModuleName+=','+CertificationRegionCodes[HardwareVerNumber[2]]
				else:ModuleName+=',%02X'%HardwareVerNumber[2]
		else:
			ModuleName=""
			if HardwareVerNumber[0]==0x31:ModuleName+="E710"
			elif HardwareVerNumber[0]==0x32:ModuleName+="E510"
			elif HardwareVerNumber[0]==0x33:ModuleName+="E310"
			elif HardwareVerNumber[0]==0x34:ModuleName+="E910"
			elif HardwareVerNumber[0]==0xB1:ModuleName+="FM13RD1616国标"
			elif HardwareVerNumber[0]==0xB3:ModuleName+="FM13RD1616国军标"
			else:ModuleName+='%02X'%HardwareVerNumber[0]
			if HardwareVerNumber[1]==0x00:ModuleName+=",单天线SIMx100"#固件(SMP/SIMx100)
			elif HardwareVerNumber[1]==0x01:ModuleName+=",双天线SIMx110"#固件(SMD/MiniTP)
			elif HardwareVerNumber[1]==0x02:ModuleName+=",四天线SIMx200"#固件(SMP/SIMx100)
			elif HardwareVerNumber[1]==0x03:ModuleName+=",八天线SIMx300"#固件(SMP/SIMx100)
			elif HardwareVerNumber[1]==0x04:ModuleName+=",十六天线SIMx400"#固件(SMP/SIMx100)
			elif HardwareVerNumber[1]==0x10:ModuleName+=",28*28贴片SIMx500旧"#固件(SMP/SIMx100)
			elif HardwareVerNumber[1]==0x20:ModuleName+=",21*21贴片SIMx600旧"#固件(SMD/MiniTP)
			elif HardwareVerNumber[1]==0x30:ModuleName+=",16*16贴片SIMx800旧/10*21贴片SIMx900旧"#固件(SMD/MiniTP)
			elif HardwareVerNumber[1]==0x40:ModuleName+=",21*21贴片SIMx600新"#20250728 add#固件(SMD/MiniTP)
			elif HardwareVerNumber[1]==0x50:ModuleName+=",16*16贴片SIMx800新"#20250728 add#固件(SMD/MiniTP)
			elif HardwareVerNumber[1]==0x60:ModuleName+=",10*21贴片SIMx900新"#20250728 add#固件(SMD/MiniTP)
			elif HardwareVerNumber[1]==0x70:ModuleName+=",28*28贴片SIMx500新"#20260115 add#固件(SMD/MiniTP)
			#后续小模块将会使用没有晶振的SMD/MiniTP
			else:ModuleName+=',%02X'%HardwareVerNumber[1]
			if HardwareVerNumber[2]:
				if HardwareVerNumber[2]in CertificationRegionCodes:ModuleName+=','+CertificationRegionCodes[HardwareVerNumber[2]]
				else:ModuleName+=',%02X'%HardwareVerNumber[2]
			if HardwareVerNumber[3]:
				if HardwareVerNumber[3]==0x20:
					ModuleName+='无委'#900M通道贴了SRRC滤波器
				elif HardwareVerNumber[3]&0x20==0x20:
					ModuleName+='无委,%02X'%HardwareVerNumber[3]
				elif HardwareVerNumber[3]==0x30:
					ModuleName+='无委+日本'#900M通道贴了SRRC滤波器，全频段贴日本滤波器
				elif HardwareVerNumber[3]&0x30==0x30:
					ModuleName+='无委+日本,%02X'%HardwareVerNumber[3]
				elif HardwareVerNumber[3]==0x40:
					ModuleName+='SIMx700外观/天线一体(陶瓷体45*45/整体50*50)'#没有软件策略
				elif HardwareVerNumber[3]==0x41:
					ModuleName+='SIMx700外观/天线一体(陶瓷体40*40/整体45.5*45.5)'#没有软件策略
				elif HardwareVerNumber[3]==0x42:
					ModuleName+='SIMx700外观/天线一体(陶瓷体35*35/整体40*40)'#没有软件策略
				elif HardwareVerNumber[3]==0x43:
					ModuleName+='SIMx700外观/天线一体(整体70*70)'#没有软件策略
				elif HardwareVerNumber[3]&0x40==0x40:
					ModuleName+='SIMx700外观/天线一体(新型号未知)'#没有软件策略
				else:
					ModuleName+=',%02X'%HardwareVerNumber[3]
				"""
				注:下述没说明的通道都是贴了直通电阻
				3?????00，900M通道贴了FCC滤波器，800M通道贴了CE_LOW滤波器。或者三个直通电阻
				3?????20，无委，900M通道贴了SRRC滤波器
				3?????30，无委+日本，900M通道贴了SRRC滤波器，全频段贴日本滤波器
				3?20??40，SIMx700(SMD/MiniTP固件)天线一体外观(陶瓷体45*45/整体50*50)
				3?00??40，SIMx700V1(SMP/SIMx100固件)天线一体外观(陶瓷体45*45/整体50*50)
				3?00??41，SIMx700V2(SMP/SIMx100固件)天线一体外观(陶瓷体40*40/整体45.5*45.5)(需要5V使能)
				3?00??42，SIMx700V3(SMP/SIMx100固件)天线一体外观(陶瓷体35*35/整体40*40)
				3?00??43，SIMx700V4(SMP/SIMx100固件)天线一体外观(整体70*70)
				"""
			print(f'在{layer}获取版本特殊情况{ModuleName} read_msg:'+Bytes2HEX(read_msg,sep=''))
	else:
		print(f'在{layer}获取版本失败 read_msg:'+Bytes2HEX(read_msg,sep=''))
		ModuleName="获取模块名称失败"
	return ModuleName
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

def GetModuleSerialNumber(rdr,P=True):
	DataTransport(rdr,build_command(0x10, [0x00, 0x00]))
	read_msg=DataReceive(rdr)
	if P:print('Successful'if len(read_msg)==0x0C+7 and check_zero(read_msg[3:5]) else'Error',end='',flush=True)
	if P:print('获取序列号 read_msg:'+Bytes2HEX(read_msg,sep=''))
	if len(read_msg)==0x0C+7 and check_zero(read_msg[3:5]):
		if P:print('Serial   Number全:'+Bytes2HEX(read_msg[5:-2]))
		if all(x<10 for x in read_msg[5:-2])and is_valid_date(''.join(['%d'%i for i in read_msg[5:5+8]])):
			SN=''.join(['%d'%i for i in read_msg[5:-2]])
			if P:print('Serial   Number旧:'+SN[:4]+' '+SN[4:6]+' '+SN[6:8]+' '+SN[8:])
			if P:print('Serial   Number旧:'+SN[2:])
			SN=SN[2:]
		elif read_msg[8]in(0x10,0x30,0x40,0x84):
			SN='%02X%02X%02X%02X%02X'%(read_msg[8],read_msg[11],read_msg[12],read_msg[15],read_msg[16])
			if P:print('Serial   Number新:'+SN[:2]+' '+SN[2:6]+' '+SN[6:])
			if P:print('Serial   Number新:'+SN)
		else:
			if P:print('序列号错误,新旧规则都不符合!')
			SN=Bytes2HEX(read_msg[5:-2],sep='')
		return SN
	else:
		return'无法获取'+Bytes2HEX(read_msg,sep='')
def GetLayer(rdr,P=True,R=0):
	#获取读写器运行阶段(0x0C)
	DataTransport(rdr,build_command(0x0C))
	read_msg=DataReceive(rdr)
	if isinstance(read_msg,list):read_msg=read_msg[0]
	r'''
	if not read_msg:
		print('获取读写器运行阶段read_msg为空')
		time.sleep(0.05)
		if R>=2:
			pause()
			return 0x900C
		else:
			# if IsSerial(rdr):rdr.flushInput()
			DataReceiveAll(rdr)
			return GetLayer(rdr,P=P,R=R+1)
	'''
	# print(f'GetLayer:获取读写器运行阶段 read_msg:'+Bytes2HEX(read_msg,sep=''))
	if len(read_msg)>=7 and read_msg[2]==0x0C and check_zero(read_msg[3:5]):
		layer='APP层'if read_msg[-3]==0x12 else'BOOT层'if read_msg[-3]==0x11 else'错误'
		if P:print(f"获取读写器运行阶段{layer} read_msg:"+Bytes2HEX(read_msg,sep=''))
		#0x11表示Bootloader层; 0x12表示APP Firmware层
		return read_msg[-3]
	elif bytes(read_msg)==bytes.fromhex('FF000CFF1FBA53'):#若len=0且错误码为FF1F则认为在APP层
		print(f'获取读写器运行阶段应用层错误 read_msg:'+Bytes2HEX(read_msg,sep=''))
		return 0x12
	else:
		if read_msg:print(f"获取读写器运行阶段!错!{R} read_msg:"+Bytes2HEX(read_msg,sep=''))
		else:print('获取读写器运行阶段read_msg为空');time.sleep(0.05)
		if R>=2:
			pause()
			return 0x900C
		else:
			# time.sleep(0.05)
			# if IsSerial(rdr):rdr.flushInput()
			DataReceiveAll(rdr)
			return GetLayer(rdr,P=P,R=R+1)
def GetStandbyPowermode(rdr,P=True):
	DataTransport(rdr,build_command(0x03))
	read_msg=DataReceive(rdr)
	if len(read_msg)==27 and check_zero(read_msg[3:5]):
		if read_msg[13:13+4]>=b'\x20\x24\x05\x23':
			# if P:print("当前固件>=20240523，支持获取待机低功耗")
			pass
		else:
			if P:print("当前固件<20240523，不支持获取待机低功耗")
			return -1
	else:
		print("获取待机低功耗!错! read_msg:"+Bytes2HEX(read_msg,sep=''))
		return -1
	DataTransport(rdr,build_command(0x68))
	read_msg=DataReceive(rdr)
	if len(read_msg)==8 and check_zero(read_msg[3:5]):
		if P:print(f'成功获取待机低功耗Power Mode={read_msg[5]}')
		return read_msg[5]
	else:
		if P:print('失败获取待机低功耗,read_msg:'+Bytes2HEX(read_msg,sep=''))
		return -1
def SetStandbyPowermode(rdr,Powermode,P=True):
	if Powermode not in (0,1,2,3):
		print(f'禁止的Powermode={Powermode}')
		return 0
	DataTransport(rdr,build_command(0x03))
	read_msg=DataReceive(rdr)
	if len(read_msg)==27 and check_zero(read_msg[3:5]):
		if read_msg[13:13+4]>=b'\x20\x24\x05\x23':
			# if P:print("当前固件>=20240523，支持设置待机低功耗")
			pass
		else:
			if P:print("当前固件<20240523，不支持设置待机低功耗")
			return -1
	else:
		print("设置待机低功耗!错! read_msg:"+Bytes2HEX(read_msg,sep=''))
		return -1
	DataTransport(rdr,build_command(0x98, [Powermode]))
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		print(f'成功设置待机低功耗Powermode={Powermode}')
	else:
		print(f'失败设置待机低功耗Powermode={Powermode}')
	return Powermode
def Getbaudrate(rdr,P=True):
	if GetLayer(rdr,P=P)!=0x12:
		print('当前不在APP层，无法获取波特率')
		return 0
	if DataTransport(rdr,build_command(0xAA40,[0x06,0x00]))<0:
		if P:print('发送获取波特率指令失败')
		return 0
	read_msg=DataReceive(rdr)
	valid_response=(len(read_msg)==25 and read_msg[1]==18 and read_msg[2]==0xAA
		and check_zero(read_msg[3:5]) and read_msg[5:15]==b'Moduletech'
		and read_msg[15:19]==b'\xAA\x40\x06\x00')
	if valid_response:
		baudrate=int.from_bytes(read_msg[-6:-2],byteorder='big')
		if baudrate in _SUPPORTED_BAUDRATES:
			if P:print(f'成功获取波特率{baudrate}')
			return baudrate
	if P:print('失败获取波特率,read_msg:'+Bytes2HEX(read_msg,sep=''))
	return 0
def Setbaudrate(rdr,baudrate,P=True):
	if GetLayer(rdr,P=False)!=0x12:
		print('当前不在APP层，无法设置波特率')
		return -1
	if type(baudrate)is not int or baudrate not in _SUPPORTED_BAUDRATES:
		print(f'禁止的波特率{baudrate}')
		return -1
	start_write_time=time.perf_counter()
	if DataTransport(rdr,build_command(0xAA40,[0x06,0x01]+list(baudrate.to_bytes(4,'big'))))<0:
		print(f'发送修改波特率{baudrate}指令失败')
		return -1
	read_msg=DataReceive(rdr)
	if not(len(read_msg)>=7 and check_zero(read_msg[3:5])):
		print(f'失败修改波特率{baudrate}')
		return -1
	else:
		if P:print(f'成功耗费{(time.perf_counter()-start_write_time)*1000:.3f}ms修改波特率{baudrate}')
		return baudrate
def SetTarget(rdr,target,P=True):
	if not isinstance(target,str):
		print(f'不支持的Target类型:{type(target).__name__}')
		return -1
	target=target.strip().upper()
	target_commands={
		'A':[0x05,0x01,0x01,0x00],
		'B':[0x05,0x01,0x01,0x01],
		'AB':[0x05,0x01,0x00,0x00],
		'A-B':[0x05,0x01,0x00,0x00],
		'A->B':[0x05,0x01,0x00,0x00],
		'BA':[0x05,0x01,0x00,0x01],
		'B-A':[0x05,0x01,0x00,0x01],
		'B->A':[0x05,0x01,0x00,0x01],
	}
	if target not in target_commands:
		print(f'不支持的Target={target}')
		return -1
	if DataTransport(rdr,build_command(0x9B,target_commands[target]))<0:
		print(f'设置Target发送失败:{target}')
		return -1
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:print(f"设置Target成功:{target}",)
		return 0
	else:
		print("设置Target失败,read_msg:"+Bytes2HEX(read_msg,sep=''))
		pause()
		return -1
def SetSel(rdr,Sel,P=True):
	if isinstance(Sel,str):
		Sel=Sel.upper().replace(' ','')
		if Sel in('ALL0','0','0X00'):Sel=0x00
		elif Sel in('ALL','ALL1','1','0X01'):Sel=0x01
		elif Sel in('~SL','NOTSL','2','0X02'):Sel=0x02
		elif Sel in('SL','3','0X03'):Sel=0x03
		else:
			print(f'不支持的Sel={Sel}')
			return -1
	if not isinstance(Sel,int)or Sel not in(0x00,0x01,0x02,0x03):
		print(f'不支持的Sel={Sel}')
		return -1
	DataTransport(rdr,build_command(0x9B,[0x05,0xA1,Sel]))
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:print(f"设置Sel成功:{Sel:02X}",)
		return 0
	else:
		print("设置Sel失败,read_msg:"+Bytes2HEX(read_msg,sep=''))
		return -1
def _GenKilowayMultiTagLightActionList(TagEPCID,Action=None):
	if not isinstance(TagEPCID,list):
		print(f'TagEPCID必须是数组，当前是{type(TagEPCID).__name__}')
		return [],[]
	TagEPCIDBytesList=[]
	for CurrentTagEPCID in TagEPCID:
		if isinstance(CurrentTagEPCID,(list,bytes,str)):pass
		else:
			print(f'TagEPCID数组内元素类型错误:{type(CurrentTagEPCID).__name__}')
			return [],[]
		CurrentTagEPCIDBytes,DataError=parse_data(CurrentTagEPCID)
		if DataError:
			print(f'TagEPCID解析失败:{DataError}')
			return [],[]
		if not CurrentTagEPCIDBytes:
			print('TagEPCID不能为空')
			return [],[]
		if len(CurrentTagEPCIDBytes)*8>0xFF:
			print(f'TagEPCID长度超过255bit:{len(CurrentTagEPCIDBytes)*8}')
			return [],[]
		TagEPCIDBytesList.append(CurrentTagEPCIDBytes)
	if Action is None:
		ActionList=[0]
		if len(TagEPCIDBytesList)>=2:ActionList+=[1]*(len(TagEPCIDBytesList)-1)
	elif isinstance(Action,int):
		if Action<0 or Action>0x07:
			print(f'Action超出范围{Action},必须是0b000~0b111')
			return [],[]
		ActionList=[Action]*len(TagEPCIDBytesList)
	elif isinstance(Action,list):
		if len(Action)!=len(TagEPCIDBytesList):
			print(f'Action数组长度{len(Action)}与TagEPCID数量{len(TagEPCIDBytesList)}不一致')
			return [],[]
		ActionList=[]
		for CurrentAction in Action:
			if not isinstance(CurrentAction,int)or CurrentAction<0 or CurrentAction>0x07:
				print(f'Action数组内元素超出范围{CurrentAction},必须是0b000~0b111')
				return [],[]
			ActionList.append(CurrentAction)
	else:
		print(f'不支持的Action类型:{type(Action).__name__}')
		return [],[]
	return TagEPCIDBytesList,ActionList
def SetKilowayMultiTagLight(rdr,Antenna,Power,TagEPCID,Action=None,P=True):
	if not isinstance(Antenna,int)or not(1<=Antenna<=16):
		print(f'Antenna={Antenna}错误，必须是1~16的整数')
		return -1
	if not isinstance(Power,int)or not(0<=Power<=3300):
		print(f'Power={Power}错误，必须是0~3300的整数')
		return -1
	TagEPCIDBytesList,ActionList=_GenKilowayMultiTagLightActionList(TagEPCID,Action=Action)
	if not TagEPCIDBytesList:return -1
	if len(TagEPCIDBytesList)>12:
		print(f'TagEPCID数量超过12个:{len(TagEPCIDBytesList)}')
		return -1
	SubData=[0xCC,0xCC,0x00,0x00,0x00,0x00,0x00,0x00]
	SubData.append(len(TagEPCIDBytesList))
	SubData.extend((1<<(Antenna-1)).to_bytes(2,'big'))
	SubData.extend([0x00,0x00,0x00,0x00])
	SubData.extend(Power.to_bytes(2,'big'))
	for CurrentAction,CurrentTagEPCIDBytes in zip(ActionList,TagEPCIDBytesList):
		SubData.append(0x04)
		SubData.append(CurrentAction)
		SubData.append(0x01)
		SubData.extend([0x00,0x00,0x00,0x20])
		SubData.append(len(CurrentTagEPCIDBytes)*8)
		SubData.extend(CurrentTagEPCIDBytes)
		SubData.append(0x00)
	send_data=build_command(0xAA4D,SubData)
	if P:print('KilowayMultiTagLight='+Bytes2HEX(send_data))
	DataTransport(rdr,send_data)
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:print(f"设置凯路威多标签亮灯成功:Antenna={Antenna},Power={Power},Action={ActionList},TagCount={len(TagEPCIDBytesList)},TagEPCID:",end='')
		if P:
			for CurrentTagEPCIDBytes in TagEPCIDBytesList:print(f"{Bytes2HEX(CurrentTagEPCIDBytes)}",end=' ')
		if P:print()
		return 0
	else:
		print("设置凯路威多标签亮灯失败,read_msg:"+Bytes2HEX(read_msg,sep=''))
		return -1
def SetCarrierAntennaPower(rdr,Antenna,Power,P=True):
	"""
	配置载波用的天线与功率（AA04扩展指令）
	:param rdr: 读写器连接对象
	:param Antenna: 天线号，1~16
	:param Power: 功率，0~3300
	:param P: 是否打印信息
	:return: 0成功，-1失败
	"""
	if not isinstance(Antenna,int)or not(1<=Antenna<=16):
		print(f'Antenna={Antenna}错误，必须是1~16的整数')
		return -1
	if not isinstance(Power,int)or not(0<=Power<=3300):
		print(f'Power={Power}错误，必须是0~3300的整数')
		return -1
	SubData=[0x0C,0x00,0x00,0x00,Antenna,0x00,0x00]
	SubData.extend(Power.to_bytes(2,'big'))
	send_data=build_command(0xAA04,SubData)
	if P:print('SetCarrierAntennaPower='+Bytes2HEX(send_data))
	DataTransport(rdr,send_data)
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:print(f"设置载波天线功率成功:Antenna={Antenna},Power={Power}")
		return 0
	else:
		print("设置载波天线功率失败,read_msg:"+Bytes2HEX(read_msg,sep=''))
		return -1
def SetCarrierFrequency(rdr,FrequencykHz,P=True):
	"""
	配置载波用的跳频表内的频率（AA27扩展指令）
	:param rdr: 读写器连接对象
	:param FrequencykHz: 频率，单位kHz，例如902750
	:param P: 是否打印信息
	:return: 0成功，-1失败
	"""
	if type(FrequencykHz)is not int:
		print(f'FrequencykHz={FrequencykHz}错误，必须是整数')
		return -1
	if not(0<=FrequencykHz<=0xFFFFFF):
		print(f'FrequencykHz={FrequencykHz}错误，无法使用3字节编码')
		return -1
	if not(780000<=FrequencykHz<=1000000):
		print(f'警告：FrequencykHz={FrequencykHz}需要在780000~1000000kHz的常用范围内')
	SubData=[0x00,0x00,0x00,0x00,0x00]
	SubData.extend(FrequencykHz.to_bytes(3,'big'))
	send_data=build_command(0xAA27,SubData)
	if P:print('SetCarrierFrequency='+Bytes2HEX(send_data))
	if DataTransport(rdr,send_data)<0:
		if P:print('设置载波频率发送失败')
		return -1
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:print(f"设置载波频率成功:FrequencykHz={FrequencykHz}")
		return 0
	else:
		print("设置载波频率失败,read_msg:"+Bytes2HEX(read_msg,sep=''))
		return -1
def SetCarrierMode(rdr,Mode,P=True):
	"""
	统一载波控制函数（AA31扩展指令）
	:param rdr: 读写器连接对象
	:param Mode: 载波模式
	             - "CW" / "cw" / 0x01: 开启载波
	             - "MCW" / "mcw" / 0xAA: 开启调制波
	             - "OFF" / "off" / 0x00: 停止关闭载波调制波
	:param P: 是否打印信息
	:return: 0成功，-1失败
	"""
	if isinstance(Mode,str):
		Mode=Mode.strip().upper()
		if Mode=="CW":Mode=0x01
		elif Mode=="MCW":Mode=0xAA
		elif Mode=="OFF":Mode=0x00
	if not isinstance(Mode,int)or Mode not in (0x00,0x01,0xAA):
		print(f'Mode={Mode}错误，必须是0x00(OFF)/0x01(CW)/0xAA(MCW)或字符串"OFF"/"CW"/"MCW"')
		return -1
	send_data=build_command(0xAA31,[Mode])
	if P:
		if Mode==0x01:print('SetCarrierMode=CW,'+Bytes2HEX(send_data))
		elif Mode==0xAA:print('SetCarrierMode=MCW,'+Bytes2HEX(send_data))
		else:print('SetCarrierMode=OFF,'+Bytes2HEX(send_data))
	DataTransport(rdr,send_data)
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:
			if Mode==0x01:print("开启载波CW成功")
			elif Mode==0xAA:print("开启调制波MCW成功")
			else:print("停止关闭载波调制波OFF成功")
		return 0
	else:
		if P:
			if Mode==0x01:print("开启载波CW失败,read_msg:"+Bytes2HEX(read_msg,sep=''))
			elif Mode==0xAA:print("开启调制波MCW失败,read_msg:"+Bytes2HEX(read_msg,sep=''))
			else:print("停止关闭载波调制波OFF失败,read_msg:"+Bytes2HEX(read_msg,sep=''))
		return -1
def SetFreqHopTable(rdr,FREQUENCY_HOPTABLE,P=True):
	DataTransport(rdr,build_command(0x95,b''.join([i.to_bytes(4,'big') for i in FREQUENCY_HOPTABLE])))
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:print(f"设置跳频表成功FreqHopTime:{FREQUENCY_HOPTABLE}",)
		return 0
	else:
		print("设置跳频表失败,read_msg:"+Bytes2HEX(read_msg,sep=''))
		return -1
def GetFreqHopTable(rdr,P=True):
	"""
	获取跳频表
	:param rdr: 读写器连接对象
	:param P: 是否打印信息
	:return: 跳频表列表，失败返回None
	"""
	DataTransport(rdr,build_command(0x65))
	read_msg=DataReceive(rdr)
	if P:print('read_msg='+Bytes2HEX(read_msg))
	if not(len(read_msg)>=7 and check_zero(read_msg[3:5])):
		if P:print("获取跳频表失败"+',read_msg:'+Bytes2HEX(read_msg,sep=' '))
		return None
	FREQUENCY_HOPTABLE=[]
	if (len(read_msg)-7)%4:
		if P:print("跳频表长度不准确，不是四的倍数"+',read_msg:'+Bytes2HEX(read_msg,sep=' '))
		return None
	for _ in range(5,len(read_msg)-2,4):
		FREQUENCY_HOPTABLE.append(int.from_bytes(read_msg[_+1:_+4],'big'))
	if P:print(f"{len(FREQUENCY_HOPTABLE):2}原始:",end='',flush=True)
	if P:print(*FREQUENCY_HOPTABLE,sep=',')
	return FREQUENCY_HOPTABLE
def GetFreqHopTime(rdr,P=True):
	DataTransport(rdr,build_command(0x65, [0x01]))
	read_msg=DataReceive(rdr)
	if len(read_msg)==12 and check_zero(read_msg[3:5]):
		FreqHopTime=int.from_bytes(read_msg[6:10],'big')
		if P:print("获取跳频时间成功FreqHopTime:",FreqHopTime)
		return FreqHopTime
	else:
		print('获取跳频时间失败,read_msg:'+Bytes2HEX(read_msg,sep=''))
		# pause()
		return -1
def SetFreqHopTime(rdr,FreqHopTime,P=True):
	DataTransport(rdr,build_command(0x03))
	read_msg=DataReceive(rdr)
	if len(read_msg)==27 and check_zero(read_msg[3:5]):
		if read_msg[11]==0x01:
			# if P:print("当前区域是FCC，允许配置跳频时间")
			pass
		else:
			# if P:print("当前区域不是FCC，不需要考虑配置跳频时间")
			return -1
		if read_msg[13:13+4]>=b'\x20\x25\x01\x14':
			# if P:print("当前固件>=20250114，支持配置FCC类跳频时间")
			pass
		else:
			# if P:print("当前固件<20250114，不支持配置FCC类跳频时间")
			return -1
	else:
		print("设置跳频时间!错! read_msg:"+Bytes2HEX(read_msg,sep=''))
		return -1
	if FreqHopTime not in(100,200,400):
		print("禁止的跳频时间,FreqHopTime:",FreqHopTime)
		# pause()
		return -1
	
	subdata=[0x01]
	subdata.extend(list(FreqHopTime.to_bytes(4,'big')))
	SetFreqHopTimeCmd=build_command(0x95, subdata)
	DataTransport(rdr,SetFreqHopTimeCmd)
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:print(f"设置跳频时间成功FreqHopTime:{FreqHopTime}",)
		return 0
	else:
		print("设置跳频时间失败,read_msg:"+Bytes2HEX(read_msg,sep=''))
		# pause()
		return -1
def GetAntClosedLoopStates(rdr,P=True):#多口模块0x61指令option=5天线口闭环状态(APP)
	DataTransport(rdr,build_command(0x61, [0x05]))
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		AntClosedLoopStates=read_msg[6:-2][1::2]
		if P and len(AntClosedLoopStates)==1:print("单口模块无法获取天线口闭环状态:"+'开闭'[AntClosedLoopStates[0]],end=',',flush=True)
		if P and len(AntClosedLoopStates)!=1:
			print("获取天线口闭环状态成功:",end='')
			for i in AntClosedLoopStates:
				cprint('闭'if i else'开','绿'if i else'红')
			print('.',end='',flush=True)
		return AntClosedLoopStates
	else:
		print("获取天线口闭环状态失败,read_msg:"+Bytes2HEX(read_msg,sep=''))
		pause()
		return []
def GetAntPortNum(rdr,P=True):#通过(APP)
	if GetLayer(rdr,P=False)==0x11:
		return GetAntPortNum2(rdr,P=P)
	AntPortNum=len(GetAntClosedLoopStates(rdr,P=P))
	if not AntPortNum:
		AntPortNum=GetAntPortNum2(rdr,P=P)
	if P:print(f'成功获取到有{AntPortNum}个天线')
	return AntPortNum
def GetAntPortNum2(rdr,P=True):#通过硬件编码获取天线口---大部分情况已弃用(BOOT or APP)
	DataTransport(rdr,build_command(0x03))
	read_msg=DataReceive(rdr)#FF 14 03 00 00 22 02 11 00 31 02 00 00 20 23 03 12 23 03 12 00 00 00 00 10 51 E2
	if len(read_msg)==27 and check_zero(read_msg[3:5]):
		HardwareVer=GetHardwareVersion(rdr,P=P)
		# print(Bytes2HEX(HardwareVer,sep=''))
		if HardwareVer[0] not in(0x31,0x32,0x33,0x34):
			ModuleName=GetModuleName(rdr,P=P)
			if ModuleName in('SLR1200','SLR1200V2','SLR1200V2-0001','SLR1219','SLR3000','SLR5100','SLR5200','SLR3100','SLR5300'):AntPortNum=1
			elif ModuleName[:3]=="SQM":AntPortNum=1
			elif ModuleName in('SLR1100','SLR5600'):AntPortNum=4
			elif ModuleName in('SLR5800','SLR5800-0001','SLR6000','SLR6000-0001'):AntPortNum=8
			elif ModuleName in('SLR5900','SLR5900-0001','SLR6100','SLR6100-0001'):AntPortNum=16
			else:AntPortNum=0
		elif HardwareVer[1]in(0x00,0x10,0x20,0x30,0x40,0x50,0x60,0x70):AntPortNum=1
		elif HardwareVer[1]==0x01:AntPortNum=2
		elif HardwareVer[1]==0x02:AntPortNum=4
		elif HardwareVer[1]==0x03:AntPortNum=8
		elif HardwareVer[1]==0x04:AntPortNum=16
		# elif HardwareVer[1]==0x05:AntPortNum=32
		else:AntPortNum=1
	else:
		AntPortNum=0
	if P:print('成功'if len(read_msg)>=7 and check_zero(read_msg[3:5]) else'失败',end='',flush=True)
	if P:print(f'获取版本,有{AntPortNum}个天线')
	return AntPortNum
def GetSupportedFrequencyBands(rdr,P=True):
	DataTransport(rdr,build_command(0x71))#获取可用频段
	read_msg=DataReceive(rdr)
	# if P:print('send_data='+Bytes2HEX(send_data))
	# if P:print('read_msg='+Bytes2HEX(read_msg))
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		Module_FrequencyBand_Codes=read_msg[5:-2]if len(read_msg)>=7 and check_zero(read_msg[3:5]) else []
		if P:print('获取可用频段成功:'+','.join(['0x%02X'%i for i in Module_FrequencyBand_Codes]))
		return Module_FrequencyBand_Codes
	else:
		print("获取可用频段失败"+',read_msg:'+Bytes2HEX(read_msg,sep=''))
		pause()
		return []
def GetFrequencyBand(rdr,P=True):
	DataTransport(rdr,build_command(0x67))#获取当前的工作频段
	read_msg=DataReceive(rdr)
	if len(read_msg)==8 and check_zero(read_msg[3:5]):
		FrequencyBandCode=read_msg[-3]
		if P:print("获取工作频段成功0x%02X:"%FrequencyBandCode,FrequencyBandCodes[FrequencyBandCode]if FrequencyBandCode in FrequencyBandCodes else"NotFound")
		return FrequencyBandCode
	else:
		print("获取工作频段失败"+',read_msg:'+Bytes2HEX(read_msg,sep=''))
		pause()
		return -1
def SetFrequencyBand(rdr,FrequencyBandCode,P=True):
	# if FrequencyBandCode not in FrequencyBandCodes:
		# print("禁止的频段编码:0x%02X"FrequencyBandCode)
		# pause()
		# return -1
	DataTransport(rdr,build_command(0x97, [FrequencyBandCode]))
	read_msg=DataReceive(rdr)
	# if P:print("SetFrequencyBandCmd="+Bytes2HEX(SetFrequencyBandCmd))
	# if P:print("read_msg="+Bytes2HEX(read_msg))
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:print("设置频段成功0x%02X:"%FrequencyBandCode+FrequencyBandCodes[FrequencyBandCode]if FrequencyBandCode in FrequencyBandCodes else"NotFound")
		return 0
	else:
		print("设置频段失败"+',read_msg:'+Bytes2HEX(read_msg,sep=''))
		# pause()
		return -1
"""
FrequencyBand=GetFrequencyBand(rdr)
SetFrequencyBand(rdr,FrequencyBand)
FreqHopTime=GetFreqHopTime(rdr)
SetFreqHopTime(rdr,FreqHopTime)
"""
def GetFrequencyHoppingTable(rdr,P=True):
	DataTransport(rdr,build_command(0x65))
	read_msg=DataReceive(rdr)
	# if P:print('Successful'if len(read_msg)>=7 and check_zero(read_msg[3:5]) and(len(read_msg)-7)%4==0 else'Error',end='',flush=True)
	# if P:print('获取跳频表 read_msg:'+Bytes2HEX(read_msg,sep=''))
	if len(read_msg)>=7 and check_zero(read_msg[3:5]) and(len(read_msg)-7)%4==0:
		if P:print(f'获取到{(len(read_msg)-7)//4}个频率',end='',flush=True)
		Frequencys=[]
		for i in range(5,len(read_msg)-2,4):
			Frequencys.append(int.from_bytes(read_msg[i:i+4],'big'))
		if P:print(*Frequencys,sep=',')
		return Frequencys
	else:
		return[]
""""""
def ParseReceivedData(datarecv):
	MAC=Bytes2HEX(datarecv[10:10+6])
	DATA=datarecv[16:]
	dhcp='启用DHCP'if DATA[0]else'静Static'
	IPaddr='.'.join("%d"%x for x in DATA[1:1+4])
	Mask='.'.join("%d"%x for x in DATA[5:5+4])
	GateWay='.'.join("%d"%x for x in DATA[9:9+4])
	DNS='.'.join("%d"%x for x in DATA[13:13+4])
	IPProt=int.from_bytes(DATA[17:19],'big')
	BoardType='hc32f460'if DATA[19]==1 else'Error'
	ModuleType=DATA[20:20+2]
	if ModuleType[0:1]in ModuleTypeFirstBytes:ModuleType=ModuleTypeFirstBytes[ModuleType[0:1]]
	elif isImpinjType(ModuleType):ModuleType=ImpinjType(ModuleType)
	else:ModuleType=Bytes2HEX(ModuleType)
	BoardFirmwareVer='.'.join("%d"%x for x in DATA[22:22+4])
	RFIDFirmwareVer=Bytes2HEX(DATA[26:26+4],sep='.')
	WorkMode="BOOT"if DATA[30]==0 else"被动Passive"if DATA[30]==1 else"主动Active"
	return MAC,dhcp,IPaddr,Mask,GateWay,DNS,IPProt,BoardType,ModuleType,BoardFirmwareVer,RFIDFirmwareVer,WorkMode
def GetLocalIPByPrefix2():
	if not TCP_AVAILABLE or not NETIFACES_AVAILABLE:
		return {}
	LocalIPs={}
	try:
		for interface in netifaces.interfaces():
			addresses=netifaces.ifaddresses(interface)
			if netifaces.AF_INET in addresses:
				LocalIPs[interface]=addresses[netifaces.AF_INET][0]['addr']
	except Exception as E:
		print('GetLocalIPByPrefix2未知异常',str(E))
		return {}
	# print(LocalIPs)
	return LocalIPs
def GetLocalIPByPrefix():
	if not TCP_AVAILABLE or not PSUTIL_AVAILABLE:
		return {}
	LocalIPs={}
	try:
		for net_if_name,net_if in psutil.net_if_addrs().items():
			for snicaddr in net_if:
				# print(snicaddr.family)
				# print(type(snicaddr.family))
				if snicaddr.family==socket.AF_INET:
					LocalIPs[net_if_name]=snicaddr.address
					break
	except Exception as E:
		print('GetLocalIPByPrefix未知异常',str(E))
		return {}
	# print(LocalIPs)
	return LocalIPs
def GetLinuxInterfaceNames():
	interface_names=[]
	try:
		if callable(getattr(socket,'if_nameindex',None)):
			interface_names=[interface_name for _,interface_name in socket.if_nameindex()]
	except Exception:
		pass
	if not interface_names:
		try:
			interface_names=os.listdir('/sys/class/net')
		except Exception:
			pass
	if not interface_names:
		try:
			with open('/proc/net/dev','r')as net_devices:
				for line in net_devices:
					if':'not in line:continue
					interface_name=line.split(':',1)[0].strip()
					if interface_name:interface_names.append(interface_name)
		except Exception:
			pass
	return sorted(set(interface_names))
def GetLocalIPByLinux():
	if not TCP_AVAILABLE or not IS_LINUX or not FCNTL_AVAILABLE:return {}
	LocalIPs={}
	try:
		with socket.socket(socket.AF_INET,socket.SOCK_DGRAM)as local_socket:
			for interface_name in GetLinuxInterfaceNames():
				try:
					interface_name_bytes=interface_name.encode()[:15]
					interface_request=interface_name_bytes+b'\x00'*(256-len(interface_name_bytes))
					interface_address=fcntl.ioctl(local_socket.fileno(),0x8915,interface_request)[20:24]
					LocalIPs[interface_name]=socket.inet_ntoa(interface_address)
				except OSError:continue
	except Exception as E:
		print('GetLocalIPByLinux未知异常',str(E))
		return {}
	return LocalIPs
def GetLocalIPs():
	if IS_LINUX:
		LocalIPs=GetLocalIPByLinux()
	else:
		LocalIPs=GetLocalIPByPrefix()
		if not LocalIPs:LocalIPs=GetLocalIPByPrefix2()
	if not LocalIPs:LocalIPs={'不绑定本机IP':''}
	return LocalIPs
def is_valid_ip(address):
	if not TCP_AVAILABLE:
		return False
	if not isinstance(address,str):return False
	try:
		return str(ipaddress.IPv4Address(address))==address
	except(ipaddress.AddressValueError,TypeError):
		return False
def extract_hid_instance_id(path_bytes:bytes) -> str:
	"""
	传入:b'\\\\?\\HID#VID_2E88&PID_4605&MI_00#a&296b7cee&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}'
	返回:'a&296b7cee'
	"""
	# 将字节串转换为字符串并分割路径组件
	path_str=path_bytes.decode('utf-8')
	components=path_str.split('#')
	
	# 确保路径格式正确
	if len(components)<4:
		raise ValueError(f"无效的HID设备路径格式:{path_str}")
	
	# 提取实例标识符部分（通常是第4个组件的前两部分）
	instance_component=components[2]
	instance_parts=instance_component.split('&')
	
	# 返回前两部分的组合
	if len(instance_parts)>=2:
		return f"{instance_parts[0]}&{instance_parts[1]}"
	else:
		return instance_parts[0] if instance_parts else ""
"""
def FindHid():#已弃用，用新的FindHidPath
	for device in hid.enumerate():
		if'manufacturer_string' in device and device['manufacturer_string']=="HDSC":
			if'path' in device:
				print('找到开发板连接的USB:'+device['path'].decode())
				# print('找到开发板的USBHID，序列号:'+extract_hid_instance_id(device['path'])+'\npath:'+device['path'].decode())
			return(device['vendor_id'],device['product_id'])
	# print('未找到开发板连接的USB')
	return(0,0)
"""
def FindHidPath():#通过唯一设备路径（含MI_00）打开，彻底避免误打开 MI_01（键盘接口）
	if not HID_AVAILABLE:
		return b''
	for device in hid.enumerate():
		hid_path=device.get('path',b'')
		if not hid_path:continue
		if isinstance(hid_path,bytes):hid_path=hid_path.decode(errors='replace')
		elif not isinstance(hid_path,str):hid_path=str(hid_path)
		macos_interface=(IS_MACOS and device.get('vendor_id')==0x2E88 and device.get('product_id')==0x4605 and device.get('interface_number')==0 and device.get('usage_page')!=0x01)
		windows_interface=(not IS_MACOS and 'MI_00'in hid_path)
		if device.get('manufacturer_string')=="HDSC"and(macos_interface or windows_interface):
			print('找到开发板连接的USB\npath:'+hid_path)
			# print(f"  路径：{device['path'].decode('utf-8')}")
			# print(f"  用途页：0x{device['usage_page']:04X}（通信接口通常为0x00或0xFF，键盘为0x01）")
			# print(f"  厂商：{device.get('manufacturer_string','未知')}")
			# print(f"  产品：{device.get('product_string','未知')}")
			# print('找到开发板的USBHID，序列号:'+extract_hid_instance_id(device['path'])+'\npath:'+device['path'].decode())
			return device['path']
	# print('未找到开发板连接的USB')
	return b''

class TimeoutThread(threading.Thread):
	def __init__(self,target,args=(),kwargs=None):
		super().__init__()
		self.target=target
		self.args=args
		self.kwargs=kwargs or{}
		self.result=None
		self.error=None
	def run(self):
		try:
			self.result=self.target(*self.args,**self.kwargs)
		except Exception as e:
			self.error=e
def run_with_timeout(func,args=(),kwargs=None,timeout=0.6):
	thread=TimeoutThread(func,args,kwargs)
	thread.daemon=True  # 设置为守护线程，主线程退出时自动终止
	thread.start()
	thread.join(timeout)  # 等待指定时间
	if thread.is_alive():
		# 超时处理（无法强制终止线程，需函数自己支持中断）
		raise TimeoutError("函数运行超时！")
	if thread.error:
		raise thread.error
	return thread.result
def _serial_close_worker(ser):
	try:ser.close()
	except Exception:pass
def _close_serial(ser,wait=True):
	try:
		if not ser.isOpen():return
	except Exception:
		return
	if IS_MACOS:
		for method_name in('cancel_read','cancel_write'):
			try:getattr(ser,method_name)()
			except Exception:pass
	if not wait:
		try:
			if getattr(ser,'_moduleapi_close_started',False):return
			ser._moduleapi_close_started=True
		except Exception:pass
		threading.Thread(target=_serial_close_worker,args=(ser,),daemon=True).start()
		return
	ser.close()
def _open_serial_auto(port,baudrate,serial_kwargs,open_timeout):
	if not IS_MACOS:
		return run_with_timeout(serial.Serial,kwargs=dict(serial_kwargs,port=port),timeout=open_timeout)
	with _MACOS_SERIAL_OPEN_LOCK:
		if port in _MACOS_SERIAL_OPEN_PENDING:raise OSError('串口打开仍在结束')
		_MACOS_SERIAL_OPEN_PENDING.add(port)
	result={}
	finished=threading.Event()
	cancelled=threading.Event()
	state_lock=threading.Lock()
	def open_worker():
		ser=None
		try:
			ser=serial.Serial(**dict(serial_kwargs,port=None))
			ser.port=port
			try:ser.dtr=False
			except Exception:pass
			try:ser.rts=False
			except Exception:pass
			ser.open()
			with state_lock:
				should_close=cancelled.is_set()
				if not should_close:result['serial']=ser
			if should_close:threading.Thread(target=_serial_close_worker,args=(ser,),daemon=True).start()
		except BaseException as E:
			result['error']=E
			if ser is not None:threading.Thread(target=_serial_close_worker,args=(ser,),daemon=True).start()
		finally:
			with _MACOS_SERIAL_OPEN_LOCK:_MACOS_SERIAL_OPEN_PENDING.discard(port)
			finished.set()
	threading.Thread(target=open_worker,daemon=True).start()
	if not finished.wait(open_timeout):
		with state_lock:
			cancelled.set()
			late_serial=result.pop('serial',None)
		if late_serial:threading.Thread(target=_serial_close_worker,args=(late_serial,),daemon=True).start()
		raise OSError('串口打开超时')
	if'error'in result:raise result['error']
	return result.get('serial')
def _close_probe_serial(ser,mode):
	if ser is not None:_close_serial(ser,wait=not(IS_MACOS and mode=='auto'))
_MACOS_SERIAL_OPEN_LOCK=threading.Lock()
_MACOS_SERIAL_OPEN_PENDING=set()
def _TryConnectSerial(port,baudrate,mode='manual',printtime=True,serial_connection=None):
	"""
	通用串口连接函数
	mode='manual': 手动模式，用更长超时，失败后可能继续其他接口
	mode='auto': 自动模式，用更短超时+run_with_timeout
	"""
	if not SERIAL_AVAILABLE:
		return None
	ser=serial_connection
	reuse_serial=ser is not None
	try:
		if ser is None and mode=='manual':
			# 手动:因为是手动输入的串口号，所以此处可以多等会儿
			ser=serial.Serial(port=port,baudrate=baudrate,timeout=0.6)
		elif ser is None:
			# 自动:使用短超时
			current_timeout,open_timeout,write_timeout=_get_serial_auto_timeouts(baudrate)
			# print(f'{now_time()}:try open serial{port}:{baudrate},current_timeout={current_timeout}')
			serial_kwargs={"port":port,"baudrate":baudrate,"timeout":current_timeout}
			if write_timeout is not None:serial_kwargs['write_timeout']=write_timeout
			ser=_open_serial_auto(port,baudrate,serial_kwargs,open_timeout)
			# ser=serial.Serial(port,baudrate,timeout=current_timeout)
			# print(f'{now_time()}:{port}:{baudrate}打开Successful')
		elif mode=='auto':
			current_timeout,open_timeout,write_timeout=_get_serial_auto_timeouts(baudrate)
			ser.baudrate=baudrate
			ser.timeout=current_timeout
			if write_timeout is not None:ser.write_timeout=write_timeout
	# except TimeoutError as E:
		# print(f'{now_time()}:{port}:{baudrate}打开超时',str(E))
		# if'ser'in locals()and ser.isOpen():ser.close()
		# continue
	except OSError as E:
		OSErrorText=str(E)
		if '拒绝访问。'in OSErrorText:
			print(f'{port}:{baudrate} 被占用，拒绝访问，请确保关闭其他程序的占用后再次尝试')
		elif '参数错误。'in OSErrorText:
			print(f'{port}:{baudrate} 参数错误，请确保该串口驱动正常，能正常打开')
		elif '系统找不到指定的路径' in OSErrorText:
			print(f'{port}:{baudrate} 系统找不到指定的路径，停止尝试该串口后续波特率')
		else:
			print(f'{port}:{baudrate} OSError',OSErrorText)
		if not reuse_serial and ser is not None:_close_probe_serial(ser,mode)
		if mode!='manual':return'OSError'
		return None
	except Exception as E:
		print(f'{port}:{baudrate} Error',str(E))
		if not reuse_serial and ser is not None:_close_probe_serial(ser,mode)
		return None
	if('ser' not in locals())or ser is None or(not ser.isOpen()):
		# print(f'{port}:{baudrate}open failed.')
		if not reuse_serial and ser is not None:_close_probe_serial(ser,mode)
		return None
	try:
		for _ in range(5):
			if mode=='manual':
				# print(f'{now_time()}:!!!Before run_with_timeout')
				transport_result=run_with_timeout(DataTransport,kwargs={"s":ser,"Data":build_command(0x03)},timeout=1)
				# if transport_result==-1:
				# 	if'ser'in locals()and ser.isOpen():ser.close()
				# 	return None
				# print(f'{now_time()}:!!!After DataTransport')
				read_msg=run_with_timeout(DataReceive,kwargs={"s":ser},timeout=1)#以解决收发短路导致收到FF00031D0C卡while内一直等待的问题
				# print(f'{now_time()}={read_msg}:!!!After DataReceive')
			else:
				# 已解决:蓝牙连接打开极其缓慢，通过计时执行打开函数
				# 只给了10ms的时间，实测9600~921600只需要3~5ms
				# 如果正常串口也报错，需要把这个时间改为,timeout=0.01)或者,timeout=current_timeout+0.5)
				transport_result=DataTransport(ser,build_command(0x03))if IS_MACOS else run_with_timeout(DataTransport,kwargs={"s":ser,"Data":build_command(0x03)},timeout=0.01)
				# if transport_result==-1:
				# 	if'ser'in locals()and ser.isOpen():ser.close()
				# 	return None
				# print(f'{now_time()}:!!!Before timeout=0.01')
				if IS_MACOS and transport_result<0:break
				read_msg=DataReceive(ser,deadline=time.perf_counter()+open_timeout)if IS_MACOS else run_with_timeout(DataReceive,kwargs={"s":ser},timeout=current_timeout+0.55)
				# print(f'{now_time()}:!!!After  timeout=0.01')
			if isinstance(read_msg,list):read_msg=read_msg[0]
			if not read_msg:
				if mode=='manual':
					print(f'手动串口{port}:{baudrate}无回应')
				else:
					pass#自动模式下，不打印无回应
					# print(f'自动串口{port}:{baudrate}无回应')
				break
			elif len(read_msg)>=7:
				if len(read_msg)==0x14+7 and read_msg[2]==3 and check_zero(read_msg[3:5]):
					if mode=='manual':
						# if printtime:print(now_time())
						print(f'{port}:{baudrate}手动成功获取版本获取版本{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
					else:
						# if printtime:print(now_time())
						print(f'{port}:{baudrate}自动成功获取版本{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
					if mode!='manual':
						# ser.flushInput()
						DataReceiveAll(ser)
					else:
						# ser.flushInput()
						pass
					settimeout(ser,1)
					if IS_MACOS:
						try:ser.write_timeout=None
						except Exception:pass
					return ser
				elif read_msg[2]==0xAA:
					if mode=='manual':
						print(f'COM手动失败获取版本AA标签{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
					else:
						print(f'COM自动失败获取版本AA标签{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
				elif read_msg[2:4]==b'\x03\xAA':
					if mode=='manual':
						print(f'COM手动失败获取版本03打断停止{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
					else:
						print(f'COM自动失败获取版本03打断停止{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
				elif read_msg[0:7]==bytes.fromhex('FF0003FF1F4BBC'):#S:FF00031D0C回复R:FF0003FF1F4BBC 在APP层运行错误，需要回BOOT
					if mode=='manual':
						print(f'COM手动失败获取版本FF1F{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
					else:
						print(f'COM自动失败获取版本FF1F{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
					DataTransport(ser,build_command(0x09))
					time.sleep(0.25)
					read_msg=DataReceive(ser)
				else:
					if mode=='manual':
						print(f'COM手动失败获取版本else{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
					else:
						print(f'COM自动失败获取版本else{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
			else:
				if mode=='manual':
					print(f'COM手动回应错误{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
				else:
					print(f'COM自动回应错误{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
			if mode=='manual':
				# ser.flushInput()
				settimeout(ser,0.1)
				DataReceiveAll(ser)
				settimeout(ser,0.4)
			else:
				# time.sleep(0.05)
				# ser.flushInput()
				DataReceiveAll(ser)
	except TimeoutError as E:
		if mode=='manual':
			print(f'{port}:{baudrate}手动读写超时:',str(E))
		else:
			# print(f'{port}:{baudrate}自动读写超时:',str(E))
			pass
		if not reuse_serial and ser is not None:_close_probe_serial(ser,mode)
		return None
	except Exception as E:
		if mode=='manual':
			print(f'{port}:{baudrate}手动读写失败:',str(E))
		else:
			# print(f'{port}:{baudrate}自动读写失败:',str(E))
			pass
		if not reuse_serial and ser is not None:_close_probe_serial(ser,mode)
		return None
	if not reuse_serial and ser is not None:_close_probe_serial(ser,mode)
	return None

def TryOpenSerial(ports,printtime=True):
	if not SERIAL_AVAILABLE:
		return None
	for port in ports:
		if not port:continue
		# print(port)
		# baudrates=[9600,19200,38400,57600,115200,230400,460800,921600][::-1]
		# baudrates=[9600,19200,38400,57600,115200,230400,460800,921600]
		baudrates=[115200,921600,460800,230400,57600,38400,19200,9600]
		if IS_MACOS:
			current_timeout,open_timeout,write_timeout=_get_serial_auto_timeouts(baudrates[0])
			serial_kwargs={"baudrate":baudrates[0],"timeout":current_timeout}
			if write_timeout is not None:serial_kwargs['write_timeout']=write_timeout
			try:ser=_open_serial_auto(port,baudrates[0],serial_kwargs,open_timeout)
			except OSError:continue
			for baudrate in baudrates:
				result=_TryConnectSerial(port,baudrate,mode='auto',printtime=printtime,serial_connection=ser)
				if result=='OSError':
					_close_probe_serial(ser,'auto')
					break
				if result:return result
			_close_probe_serial(ser,'auto')
			print(f'{port}所有波特率都无回应/发送超时')
			continue
		for baudrate in baudrates:
			result=_TryConnectSerial(port,baudrate,mode='auto',printtime=printtime)
			if result=='OSError':break
			if result:
				return result
			continue
		else:
			print(f'{port}所有波特率都无回应/发送超时')
			# print(f'串口{port}:[{",".join(map(str,baudrates))}]无回应')
	return None
def _TryConnectTCP(IPaddr,IPProt=8080,mode='manual',LocalIP=None,printtime=True):
	"""
	通用TCP连接函数
	mode='manual': 直连模式，直接连接指定IP
	mode='auto': 广播模式，先通过UDP搜索再连接
	"""
	if not TCP_AVAILABLE:
		return None
	if not is_valid_ip(IPaddr)or not is_valid_tcp_port(IPProt):
		if mode=='manual':print(f'TCP地址或端口非法:{IPaddr}:{IPProt}')
		return None
	try:
		tcp_socket=None
		tcp_socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
		tcp_socket.settimeout(0.6)
		if LocalIP and mode=='auto':
			tcp_socket.bind((LocalIP,0))
		tcp_socket.connect((IPaddr,IPProt))
	except Exception as e:
		if tcp_socket:tcp_socket.close()
		if mode=='manual':
			print('tcp_socket 连接错误2',str(e))
		else:
			print('tcp_socket 连接错误1',str(e))
		return None
	else:
		# print(f'TCP/IP连接成功,',end='',flush=True)
		if mode=='manual':
			print(f'TCP/IP手动连接成功,本机是客户端Client={tcp_socket.getsockname()[0]}:{tcp_socket.getsockname()[1]}',end=',',flush=True)
		else:
			print(f'TCP/IP自动连接成功,本机是客户端Client={tcp_socket.getsockname()[0]}:{tcp_socket.getsockname()[1]}',end=',',flush=True)
		print(f'ARM7开发板是服务器Server={tcp_socket.getpeername()[0]}:{tcp_socket.getpeername()[1]}')
		settimeout(tcp_socket,0.6)
		for _ in range(5):
			DataTransport(tcp_socket,build_command(0x03))#此处应该直接发
			read_msg=DataReceive(tcp_socket)
			if isinstance(read_msg,list):read_msg=read_msg[0]
			if not read_msg:
				if mode=='manual':
					print(f'TCP手动无回应{_}，可能是',end='')
				else:
					print(f'TCP自动无回应{_}，可能是',end='')
				cprint('ARM9','红')
				print('设备，本程序',end='')
				cprint('无法连接','红',end='\n')
				if tcp_socket:
					#此处无需重试，因为如果对面TCP开了连接，就一定会有回应。
					#如果无回应，说明连错设备了，tcp会被动断开，报出如下错误
					# DataTransport IsIP(s) s.send(bytes(Data))错误:[WinError 10054] 远程主机强迫关闭了一个现有的连接。
					tcp_socket.close()
					return None
			elif len(read_msg)>=7:
				if len(read_msg)==0x14+7 and read_msg[2]==3 and check_zero(read_msg[3:5]):
					if mode=='manual':
						# if printtime:print(now_time())
						print(f'TCP手动成功获取版本{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
					else:
						# if printtime:print(now_time())
						print(f'TCP自动成功获取版本{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
					# tcp_socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
					# tcp_socket.connect((IPaddr,IPProt))
					# settimeout(tcp_socket,0.6)
					return tcp_socket
				elif read_msg[2]==0xAA:#AA48未停止的情况-标签
					if mode=='manual':
						print(f'TCP手动失败获取版本AA标签{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
					else:
						print(f'TCP自动失败获取版本AA标签{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
				elif read_msg[2:4]==b'\x03\xAA':#AA48未停止的情况-被03打断停止的回应
					if mode=='manual':
						print(f'TCP手动失败获取版本03打断停止{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
					else:
						print(f'TCP自动失败获取版本03打断停止{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
				elif read_msg[0:7]==bytes.fromhex('FF0003FF1F4BBC'):#S:FF00031D0C回复R:FF0003FF1F4BBC 在APP层运行错误，需要回BOOT
					if mode=='manual':
						print(f'TCP手动失败获取版本FF1F{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
					else:
						print(f'TCP自动失败获取版本FF1F{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
					DataTransport(tcp_socket,build_command(0x09))
					time.sleep(0.25)
					read_msg=DataReceive(tcp_socket)
				else:
					if mode=='manual':
						print(f'TCP手动失败获取版本else{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
					else:
						print(f'TCP自动失败获取版本else{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
			else:
				if mode=='manual':
					print(f'TCP手动回应错误{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
				else:
					print(f'TCP自动回应错误{_}read_msg:'+Bytes2HEX(read_msg,sep=''))
			time.sleep(0.1)
			DataReceiveAll(tcp_socket)
		else:
			if mode=='manual':
				if printtime:print(now_time())
				print(f'{IPaddr}:{IPProt} TCP手动连接失败,5次回应错误read_msg:'+Bytes2HEX(read_msg,sep=''))
			else:
				if printtime:print(now_time())
				print(f'{IPaddr}:{IPProt} TCP自动连接失败,5次回应错误read_msg:'+Bytes2HEX(read_msg,sep=''))
		if tcp_socket:
			tcp_socket.close()
			tcp_socket=None
	# print("本机的所有网卡下都没找到设备,需要保证模块供电正常,并重新上电")
	return None

def TryOpenTCP(LocalIPs,printtime=True):
	if not TCP_AVAILABLE:
		return None
	devices_found=[]
	for LocalName,LocalIP in LocalIPs.items():
		udp_socket=None
		try:
			udp_socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
			udp_socket.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,True)
			if LocalIP:
				bind_udp_socket_to_interface(udp_socket,LocalName)
				udp_socket.bind(get_udp_bind_address(LocalIP,0))
			udp_socket.settimeout(0.6)
			udp_socket.sendto(bytes.fromhex('EE0600005001000000000000'),("255.255.255.255",15000))
			# print(udp_socket)
			while True:
				datarecv,addr=udp_socket.recvfrom(1024)
				# print(f"{addr[0]}:{addr[1]}:"+Bytes2HEX(datarecv,sep=''))
				pass
				if len(datarecv)!=47:
					print("recvdata:"+Bytes2HEX(datarecv,sep=''))
					print(f"数据长度接收错误,len(datarecv)={len(datarecv)}")
					continue
				if datarecv[:10]!=bytes.fromhex('FF06001F500000000000'):
					print("忽略UDP固定头错误的数据:"+Bytes2HEX(datarecv,sep=''))
					continue
				MAC,dhcp,IPaddr,Mask,GateWay,DNS,IPProt,BoardType,ModuleType,BoardFirmwareVer,RFIDFirmwareVer,WorkMode=ParseReceivedData(datarecv)
				MACOK=MAC.upper().startswith('0826AE1')
				IPaddrOK=is_valid_ip(IPaddr) and addr[0]==IPaddr
				addr0OK=is_valid_ip(addr[0]) and IPaddr==addr[0]
				MaskOK=is_valid_mask(Mask)
				LocalIPOK=bool(LocalIP) and is_private_lan_ip(LocalIP) and is_same_subnet(LocalIP,IPaddr,Mask)
				GateWayOK=is_valid_gateway_logic(IPaddr,Mask,GateWay)
				DNSOK=is_valid_dns_logic(DNS)
				print(f"\r{now_time()}{LocalName}=",end='')
				cprint(LocalIP,'蓝'if LocalIPOK else'红')
				cprint("收")
				cprint(addr[0],'蓝'if addr0OK else'红')
				cprint("的回应IP= ")
				cprint(IPaddr,'绿'if IPaddrOK else'红')
				cprint(f":{IPProt} 详细信息:\n")
				cprint(MAC,'绿'if MACOK else'红')
				cprint(f"-{dhcp}-")
				cprint(Mask,'蓝'if MaskOK else'红')
				cprint('-')
				cprint(GateWay,'蓝'if GateWayOK else'红')
				cprint('-')
				cprint(DNS,'蓝'if DNSOK else'红')
				cprint(f"-{ModuleType}-板{BoardFirmwareVer}-模{RFIDFirmwareVer}-")
				cprint(WorkMode,'绿'if'被动Passive'==WorkMode else('黄'if'主动Active'==WorkMode else 7),end='\n')
				# print(f"成功在LocalName='{LocalName}',LocalIP='{LocalIP}'上找到了设备:\n{addr[0]} datarecv:"+Bytes2HEX(datarecv,sep=''))
				devices_found.append((IPaddr,IPProt,LocalIP))
		except socket.timeout:
			print(f"{LocalName}:{LocalIP}寻找完毕0.6秒")
			pass
		except OSError:
			print(f"{LocalName}:{LocalIP}打开失败")
			pass
		except Exception as e:
			print(f"{LocalName}:{LocalIP}未知错误",e)
			pass
		finally:
			if udp_socket is not None:
				try:udp_socket.close()
				except:pass
	if check_zero([ip=='192.168.1.100'for ip, _,_ in devices_found]):
		devices_found.append(('192.168.1.100',8080,None))
	for IPaddr,IPProt,LocalIP in devices_found:
		result=_TryConnectTCP(IPaddr,IPProt,mode='auto',LocalIP=LocalIP,printtime=printtime)
		if result:return result
	# print("本机的所有网卡下都没找到设备,需要保证模块供电正常,并重新上电")
	return None

def _TryConnectHid(HIDPath,mode='manual',printtime=True):
	"""
	通用HID连接函数
	mode='manual' 或 'auto' 行为差异不大，主要是打印信息
	"""
	if not HID_AVAILABLE:
		return None
	h=_HidConnection(hid.device())
	_reset_hid_state(h)
	try:
		h.open_path(HIDPath)
	except OSError as e:
		_forget_hid_state(h)
		if mode=='manual':
			print('USB HID手动打开失败',str(e))
		else:
			print('USB HID自动打开失败',str(e))
		return None
	if mode=='manual':
		print('USB HID手动打开成功USBSN:'+h.get_serial_number_string())
	else:
		pass
		# print('USB HID自动打开成功USBSN:'+h.get_serial_number_string())
	for _ in range(5):
		try:
			h.write([0x00,0x05,0xFF,0x00,0x03,0x1D,0x0C,0x01,0x2B])
			R=bytes(h.read(64,600))#600ms，转换为bytes统一类型
		except Exception as E:
			if mode=='manual':
				print(f'USB HID手动读取异常{_}',str(E))
			else:
				print(f'USB HID自动读取异常{_}',str(E))
			time.sleep(0.1)
			DataReceiveAll(h)
			continue
		if len(R)==0:
			if mode=='manual':
				print(f'USB HID手动无回应{_}')
			else:
				print(f'USB HID自动无回应{_}')
			settimeout(h,0.05)
			DataReceiveAll(h)
			settimeout(h,_HID_DEFAULT_TIMEOUT)
			continue
		elif len(R)==64 and R[1]==0xff and R[3]==0x03:
			if R[:6]==b'\x1b\xff\x14\x03\x00\x00':
				if mode=='manual':
					# if printtime:print(now_time())
					print(f'USB手动成功获取版本{_}:'+Bytes2HEX(R[1:1+0x14+7]))
				else:
					# if printtime:print(now_time())
					print(f'USB自动成功获取版本{_}:'+Bytes2HEX(R[1:1+0x14+7]))
				return h
			elif R[3]==0xAA:#AA48未停止的情况-标签
				if mode=='manual':
					print(f'USB手动失败获取版本AA标签{_}R:'+Bytes2HEX(R,sep=''))
				else:
					print(f'USB自动失败获取版本AA标签{_}R:'+Bytes2HEX(R,sep=''))
			elif R[3:5]==b'\x03\xaa':#AA48未停止的情况-被03打断停止的回应
				if mode=='manual':
					print(f'USB手动失败获取版本03打断停止{_}R:'+Bytes2HEX(R,sep=''))
				else:
					print(f'USB自动失败获取版本03打断停止{_}R:'+Bytes2HEX(R,sep=''))
			elif R[1:8]==bytes.fromhex('FF0003FF1F4BBC'):#S:FF00031D0C回复R:FF0003FF1F4BBC 在APP层运行错误，需要回BOOT
				if mode=='manual':
					print(f'USB手动失败获取版本FF1F{_}R:'+Bytes2HEX(R,sep=''))
				else:
					print(f'USB自动失败获取版本FF1F{_}R:'+Bytes2HEX(R,sep=''))
				h.write([0x00,0x05,0xFF,0x00,0x09,0x1D,0x06,0x01,0x2B])
				time.sleep(0.25)
				R=bytes(h.read(64,600))#600ms，转换为bytes统一类型
			else:
				if mode=='manual':
					print(f'USB手动失败获取版本else{_}R:'+Bytes2HEX(R,sep=''))
				else:
					print(f'USB自动失败获取版本else{_}R:'+Bytes2HEX(R,sep=''))
		else:
			if mode=='manual':
				print(f'USB手动回应错误{_}R:'+Bytes2HEX(R,sep=''))
			else:
				print(f'USB自动回应错误{_}R:'+Bytes2HEX(R,sep=''))
		settimeout(h,0.05)
		DataReceiveAll(h)
		settimeout(h,_HID_DEFAULT_TIMEOUT)
	if h:
		try:h.close()
		finally:_forget_hid_state(h)
	return None

def TryOpenHid(HIDPath,printtime=True):
	return _TryConnectHid(HIDPath,mode='auto',printtime=printtime)
def FindAllSerialAndTCPAndHid(printtime=True,TrySerial=True,TryTCP=True,TryHid=True):
	print(now_time()if printtime else '','开始所有寻找可用的连接，尝试','串口'if TrySerial and SERIAL_AVAILABLE else '','网络'if TryTCP and TCP_AVAILABLE else '','USB'if TryHid and HID_AVAILABLE else '',sep='')
	if TrySerial and SERIAL_AVAILABLE:
		ports=GetSerialPorts()
		# print(ports)
		# ports=[]#测试用，让其跑到TCP/USB后面
		if'ports'in locals()and ports:
			ser=TryOpenSerial(ports,printtime=printtime)
			if ser:return ser
			# print('本机的所有串口的所有波特率都无法连接(被占用),需要保证模块供电正常,并重新上电')
		else:
			print('list_ports.comports()没有找到可用的Linux串口节点')if IS_LINUX else print('list_ports.comports()和注册表内都没有找到可以连接的串口')
	''''''
	if TryTCP and TCP_AVAILABLE:
		LocalIPs=GetLocalIPs()
		s=TryOpenTCP(LocalIPs,printtime=printtime)
		if s:return s
	''''''
	if TryHid and HID_AVAILABLE:
		try:
			# VidAndPid=FindHid()
			HIDPath=FindHidPath()
		except Exception as E:
			print('FindHidPath未知异常',str(E))
		if'HIDPath'in locals()and HIDPath:
			h=TryOpenHid(HIDPath,printtime=printtime)
			if h:return h
		else:
			pass# print('未找到开发板连接的USB')
	return None
def GetLinuxSerialAddressMaybe(serial_address):
	if not IS_LINUX:return serial_address
	serial_address_exists=os.path.exists(serial_address)
	serial_address_writable=os.access(serial_address,os.W_OK)if serial_address_exists else False
	print(f'Linux串口原始地址:{serial_address}，这个节点'+('存在'if serial_address_exists else'不存在')+'，'+('有写入权限'if serial_address_writable else'无写入权限'))
	serial_address_upper=serial_address.upper()
	maybe_address=None
	serial_address_match=re.match(r'^(?:/)?(?:DEV/)?(?:TTY)?(S|USB|ACM|AMA|FIQ|THS)(\d+)$',serial_address_upper)
	if serial_address_match:
		serial_type={'S':'S','USB':'USB','ACM':'ACM','AMA':'AMA','FIQ':'FIQ','THS':'THS'}[serial_address_match.group(1)]
		maybe_address='/dev/tty'+serial_type+serial_address_match.group(2)
	if maybe_address and maybe_address!=serial_address:
		maybe_address_exists=os.path.exists(maybe_address)
		maybe_address_writable=os.access(maybe_address,os.W_OK)if maybe_address_exists else False
		print(f'Linux串口地址大小写或格式可能错误:{serial_address}，可能应该输入:{maybe_address}，这个节点'+('存在'if maybe_address_exists else'不存在')+'，'+('有写入权限'if maybe_address_writable else'无写入权限'))
	return serial_address
def IsManualSerialAddress(serial_address):
	return _parse_manual_serial_address(serial_address)is not None

def _is_valid_serial_device_path(serial_address):
	if not isinstance(serial_address,str)or'\x00'in serial_address:return False
	windows_path=bool(re.fullmatch(r'COM[1-9]\d*',serial_address,re.IGNORECASE))
	linux_tty_path=bool(re.fullmatch(r'/dev/tty[A-Za-z0-9._-]+',serial_address))
	macos_serial_path=IS_MACOS and bool(re.fullmatch(r'/dev/(?:cu|tty)[A-Za-z0-9._-]+',serial_address))
	stable_match=re.fullmatch(r'/dev/serial/(?:by-id|by-path)/([^/]+)',serial_address)
	linux_stable_path=bool(stable_match and stable_match.group(1)not in('.','..'))
	if IS_WINDOWS:return windows_path
	if IS_LINUX:return linux_tty_path or linux_stable_path
	return windows_path or linux_tty_path or linux_stable_path or macos_serial_path

def _parse_manual_serial_address(serial_address):
	if not isinstance(serial_address,str):return None
	serial_address=serial_address.strip()
	if not serial_address:return None
	address_candidate,separator,baudrate_text=serial_address.rpartition(':')
	if separator and baudrate_text.isdecimal()and _is_valid_serial_device_path(address_candidate):
		baudrate=int(baudrate_text)
		if baudrate not in _SUPPORTED_BAUDRATES:return None
		return address_candidate,baudrate
	if _is_valid_serial_device_path(serial_address):
		return serial_address,115200
	return None

def _parse_manual_tcp_address(tcp_address):
	if not isinstance(tcp_address,str):return None
	tcp_address=tcp_address.strip()
	if not tcp_address:return None
	if tcp_address.count(':')>1:return None
	if ':'in tcp_address:
		IPaddr,IPProt_text=tcp_address.rsplit(':',1)
		if not IPProt_text.isdecimal():return None
		IPProt=int(IPProt_text)
	else:
		IPaddr=tcp_address
		IPProt=8080
	try:
		parsed_ip=str(ipaddress.IPv4Address(IPaddr))
	except(ipaddress.AddressValueError,TypeError):
		return None
	if parsed_ip!=IPaddr:return None
	if not is_valid_tcp_port(IPProt):return None
	return IPaddr,IPProt
def Create(rdraddress=None,printtime=True,TrySerial=True,TryTCP=True,TryHid=True):
	if rdraddress is None:
		return FindAllSerialAndTCPAndHid(printtime=printtime,TrySerial=TrySerial,TryTCP=TryTCP,TryHid=TryHid)
	if not isinstance(rdraddress,str):
		print(f'rdraddress输入错误,必须是字符串，当前类型:{type(rdraddress).__name__}')
		return None
	rdraddress=rdraddress.strip()
	if not rdraddress:
		return FindAllSerialAndTCPAndHid(printtime=printtime,TrySerial=TrySerial,TryTCP=TryTCP,TryHid=TryHid)
	rdraddress_upper=rdraddress.upper()
	serial_config=_parse_manual_serial_address(rdraddress)
	if serial_config is not None:#认为是串口
		if not SERIAL_AVAILABLE:
			print(f'串口功能未启用(SERIAL_AVAILABLE=False或pyserial未安装)，无法使用地址:{rdraddress}')
			return None
		COMPort,baudrate=serial_config
		if IS_WINDOWS:COMPort=COMPort.upper()
		ser=_TryConnectSerial(COMPort,baudrate,mode='manual',printtime=printtime)
		if ser:
			return ser
		else:
			return FindAllSerialAndTCPAndHid(printtime=printtime,TrySerial=True,TryTCP=False,TryHid=False)
	elif _parse_manual_tcp_address(rdraddress)is not None:#认为是IP
		if not TCP_AVAILABLE:
			print(f'TCP网口功能未启用(TCP_AVAILABLE=False或socket未安装)，无法使用地址:{rdraddress}')
			return None
		IPaddr,IPProt=_parse_manual_tcp_address(rdraddress)
		s=_TryConnectTCP(IPaddr,IPProt,mode='manual',printtime=printtime)
		if s:
			return s
		else:
			return FindAllSerialAndTCPAndHid(printtime=printtime,TrySerial=False,TryTCP=True,TryHid=False)
	elif rdraddress_upper=='USB':
		if not HID_AVAILABLE:
			print(f'USB HID功能未启用(ENABLE_HID=False或hid模块未安装)，无法使用地址:{rdraddress}')
			return None
		HIDPath=FindHidPath()
		if not HIDPath:
			print('未找到开发板连接的USB')
			return FindAllSerialAndTCPAndHid(printtime=printtime,TrySerial=False,TryTCP=False,TryHid=True)
		h=_TryConnectHid(HIDPath,mode='manual',printtime=printtime)
		if h:
			return h
		else:
			return FindAllSerialAndTCPAndHid(printtime=printtime,TrySerial=False,TryTCP=False,TryHid=True)
	else:
		print(f'rdraddress输入错误,不是合法串口/IP:端口/USB地址:{rdraddress}')
		return None

def SetSession(rdr,session,P=True):
	"""
	配置 Session
	:param rdr: 读写器连接对象
	:param session: Session编号 (0-3)
	:param P: 是否打印信息
	:return: 0成功，-1失败
	"""
	DataTransport(rdr,build_command(0x9B, [0x05,0x00,session]))
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:print(f"设置Session成功:{session}")
		return 0
	else:
		print(f"设置Session失败:{session},read_msg:"+Bytes2HEX(read_msg,sep=''))
		# pause()
		return -1

def SetMultiEpcTid(rdr,enable,P=True):
	"""
	配置同EPC多TID则产生多个
	:param rdr: 读写器连接对象
	:param enable: True启用，False禁用
	:param P: 是否打印信息
	:return: 0成功，-1失败
	"""
	DataTransport(rdr,build_command(0x9A, [0x01,0x08,0x01 if enable else 0x00]))
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:print(f"设置同EPC多TID成功:{enable}")
		return 0
	else:
		print(f"设置同EPC多TID失败:{enable},read_msg:"+Bytes2HEX(read_msg,sep=''))
		# pause()
		return -1

def EnableAntennas(rdr,antennas,P=True):
	"""
	启用天线
	:param rdr: 读写器连接对象
	:param antennas: 天线列表，如 [1,2,3]
	:param P: 是否打印信息
	:return: 0成功，-1失败
	"""
	data=[0x02]
	for ant in antennas:
		data.extend([ant,ant])
	DataTransport(rdr,build_command(0x91,bytes(data)))
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:print(f"启用天线成功:{antennas}")
		return 0
	else:
		print(f"启用天线失败:{antennas},read_msg:"+Bytes2HEX(read_msg,sep=''))
		# pause()
		return -1

def GetAntennaPowerRange(rdr,P=True):
	"""
	获取天线功率范围
	:param rdr: 读写器连接对象
	:param P: 是否打印信息
	:return: (max_power, min_power) 成功，(None, None) 失败
	"""
	if DataTransport(rdr,build_command(0x62,[0x01]))<0:
		if P:print('获取天线功率范围发送失败')
		return (None,None)
	read_msg=DataReceive(rdr)
	if (len(read_msg)==14 and read_msg[1]==7 and read_msg[2]==0x62
		and check_zero(read_msg[3:5]) and read_msg[5]==0x01):
		# 数据域: [01, 0C, E4, 0C, E4, 00, 00]
		# 其中首个0C E4不用管，后面的0C E4是最大功率，00 00是最小功率
		data=read_msg[5:-2]
		max_power=int.from_bytes(data[3:5],'big')
		min_power=int.from_bytes(data[5:7],'big')
		if P:print(f"获取天线功率范围成功: 最大功率={max_power}, 最小功率={min_power}")
		return (max_power,min_power)
	if P:print(f"获取天线功率范围失败,read_msg:"+Bytes2HEX(read_msg,sep=''))
	return (None, None)

def SetAntennaPower(rdr,power_config,P=True):
	"""
	配置天线功率
	:param rdr: 读写器连接对象
	:param power_config: 功率配置，支持多种格式：
	                   - 3300: 所有天线读写功率都为3300
	                   - -1: 所有天线使用最大允许功率
	                   - [2000, 3000]: 所有天线读功率2000，写功率3000
	                   - [[1200, 2200], [1300, 2300]]: 天线1读写[1200,2200]，天线2读写[1300,2300]...
	:param P: 是否打印信息
	:return: 0成功，-1失败
	"""
	# 获取天线口数
	ant_num=GetAntPortNum(rdr,P=False)
	if type(ant_num)is not int or not(1<=ant_num<=16):
		if P:print("获取天线口数失败")
		return -1

	def valid_power(power):
		return type(power)is int and 0<=power<=3300

	# 构建天线功率配置列表
	power_list=[]
	if type(power_config)is int:
		if power_config==-1:
			max_power,_=GetAntennaPowerRange(rdr,P=False)
			if not valid_power(max_power):
				if P:print("获取最大允许功率失败")
				return -1
			power_config=max_power
		elif not valid_power(power_config):
			if P:print(f"错误：功率值必须是0~3300的整数或-1，当前值:{power_config}")
			return -1
		for ant in range(1,ant_num+1):
			power_list.append([ant,power_config,power_config])
	elif isinstance(power_config,list):
		if not power_config:
			if P:print("错误：功率配置列表不能为空")
			return -1
		if isinstance(power_config[0],(list,tuple)):
			if len(power_config)>ant_num:
				if P:print(f"错误：功率配置数量({len(power_config)})超过天线口数({ant_num})")
				return -1
			for index,power_pair in enumerate(power_config):
				if (not isinstance(power_pair,(list,tuple))or len(power_pair)!=2
					or not all(valid_power(power)for power in power_pair)):
					if P:print(f"错误：天线{index+1}功率配置必须是两个0~3300整数:{power_pair}")
					return -1
				power_list.append([index+1,power_pair[0],power_pair[1]])
		else:
			if len(power_config)!=2 or not all(valid_power(power)for power in power_config):
				if P:print(f"错误：公共功率配置必须是两个0~3300整数:{power_config}")
				return -1
			for ant in range(1,ant_num+1):
				power_list.append([ant,power_config[0],power_config[1]])
	else:
		if P:print(f"错误：不支持的功率配置类型:{type(power_config).__name__}")
		return -1

	# 构建发送数据
	data=[0x03]
	for item in power_list:
		ant, read_power, write_power = item
		data.append(ant)
		data.extend(list(read_power.to_bytes(2, 'big')))
		data.extend(list(write_power.to_bytes(2, 'big')))
	
	if DataTransport(rdr,build_command(0x91,bytes(data)))<0:
		if P:print(f"配置天线功率发送失败:{power_config}")
		return -1
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:
			print(f"配置天线功率成功:")
			for item in power_list:
				print(f"  天线{item[0]}: 读功率={item[1]}, 写功率={item[2]}")
		return 0
	else:
		print(f"配置天线功率失败:{power_config},read_msg:"+Bytes2HEX(read_msg,sep=''))
		# pause()
		return -1

def SetQ(rdr,q_params,P=True):
	"""
	配置 Q 值
	:param rdr: 读写器连接对象
	:param q_params: Q参数数组
	              [0] - 自动Q
	              [1, Q值] - 手动Q 0~15
	              [0, StartQ] - 自动Q带起始Q
	              [0, StartQ, MaxQ, MinQ] - 自动Q带起始Q+最大Q+最小Q
	:param P: 是否打印信息
	:return: 0成功，-1失败
	"""
	DataTransport(rdr,build_command(0x9B, [0x05, 0x12]+list(q_params)))
	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:print(f"设置Q值成功:{q_params}")
		return 0
	else:
		print(f"设置Q值失败:{q_params},read_msg:"+Bytes2HEX(read_msg,sep=''))
		# pause()
		return -1

def GetRFMode(rdr,P=True):
	"""
	获取 RF 模式
	:param rdr: 读写器连接对象
	:param P: 是否打印信息
	:return: RF模式数组，失败返回[]
	"""
	DataTransport(rdr,build_command(0x6B, [0x05,0x02]))
	read_msg=DataReceive(rdr)
	if P:print('获取RF模式 read_msg:'+Bytes2HEX(read_msg))
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		# 解析数据域
		data = read_msg[5:-2]
		if len(data) >= 3 and data[0] == 0x05 and data[1] == 0x02:
			if len(data) == 3:
				# 单字节
				result = [data[2]]
				if P: print(f"获取RF模式成功:0x{data[2]:02X}")
				return result
			elif len(data) == 4:
				# 双字节
				result = [data[2], data[3]]
				if P: print(f"获取RF模式成功:0x{data[2]:02X}{data[3]:02X}")
				return result
	if P: print("获取RF模式失败")
	return []

def SetRFMode(rdr,rf_mode,P=True):
	"""
	配置 RF 模式
	:param rdr: 读写器连接对象
	:param rf_mode: RF模式数组，单字节(如[0x6b])或双字节(如[0x01,0x43])，单字节时也支持直接传入数字
	:param P: 是否打印信息
	:return: 永远返回列表，成功返回当前RF模式列表，失败返回[-1]
	"""
	if type(rf_mode)is int:
		rf_mode=[rf_mode]
	elif not isinstance(rf_mode,list):
		if P: print(f"错误：RF模式必须传入数组形式或单字节数字，当前类型:{type(rf_mode)}")
		return [-1]
	else:
		rf_mode=list(rf_mode)
	if len(rf_mode)not in(1,2):
		if P:print(f"错误：RF模式列表长度必须为1或2，当前长度:{len(rf_mode)}")
		return [-1]
	if any(type(value)is not int or not(0<=value<=0xFF)for value in rf_mode):
		if P:print(f"错误：RF模式元素必须是0~255的整数:{rf_mode}")
		return [-1]

	if len(rf_mode)==1:
		# 单字节列表
		send_data=build_command(0x9B,[0x05,0x02,rf_mode[0]])
		rf_mode_hex = f"0x{rf_mode[0]:02X}"
	else:
		# 双字节列表
		send_data=build_command(0x9B,[0x05,0x02,rf_mode[0],rf_mode[1]])
		rf_mode_hex = f"0x{rf_mode[0]:02X}{rf_mode[1]:02X}"
	if DataTransport(rdr,send_data)<0:
		if P:print(f"设置RF模式发送失败:{rf_mode_hex}")
		return [-1]

	read_msg=DataReceive(rdr)
	if len(read_msg)>=7 and check_zero(read_msg[3:5]):
		if P:print(f"设置RF模式成功:{rf_mode_hex}")
		
		# 立即获取并验证
		get_mode = GetRFMode(rdr, P=False)
		if get_mode in([],[-1])or not isinstance(get_mode,list):
			if P: print("验证失败：无法获取RF模式")
			return [-1]
		
		# 对比
		if get_mode == rf_mode:
			# if P: print("验证成功：设置与获取的RF模式一致")
			return get_mode
		print(f"验证失败：设置的RF模式({rf_mode})与获取的RF模式({get_mode})不一致")
		return [-1]
	else:
		print(f"设置RF模式失败:{rf_mode_hex},read_msg:"+Bytes2HEX(read_msg,sep=''))
		# pause()
		return [-1]

def FixedFrequency(rdr,fre_index,P=True):
	"""
	配置固定频率
	:param rdr: 读写器连接对象
	:param fre_index: 频率索引，0=恢复全部，1-N=选择对应频率
	:param P: 是否打印信息
	:return: 0成功，-1失败
	"""
	if type(fre_index)is not int or fre_index<0:
		if P:print(f"频率索引必须是非负整数:{fre_index}")
		return -1
	# 获取当前频段
	current_band = GetFrequencyBand(rdr, P=False)
	if current_band == -1:
		if P: print("获取当前频段失败")
		return -1
	
	# 设置当前频段
	if SetFrequencyBand(rdr,current_band,P=P)!=0:
		if P:print("重新设置当前频段失败")
		return -1
	
	# 获取跳频表
	frequencies = GetFreqHopTable(rdr, P=False)
	if frequencies is None:
		if P: print("获取跳频表失败")
		return -1
	
	if P: print(f'跳频表:{frequencies}')
	
	if fre_index == 0:
		# fre_index为0时，已获取当前频段、设置当前频段、获取跳频表
		return 0
	else:
		# fre_index为1或2等，选择对应频率
		if fre_index < 1 or fre_index > len(frequencies):
			if P: print(f"传入的下标过大，为{fre_index}，但可配置的频率只有{frequencies}这{len(frequencies)}个")
			return -1
		
		frequencie = frequencies[fre_index-1]
		
		# 首先尝试使用 SetFreqHopTable 设置单个跳频表
		single_hop_table = [frequencie]
		result = SetFreqHopTable(rdr, single_hop_table, P=False)
		
		if result == 0:
			# 设置单个跳频表成功，验证
			if P: print("设置单个跳频表成功")
		else:
			# 设置单个跳频表失败，使用 AA27 指令
			if P: print("设置单个跳频表失败，尝试使用 AA27 指令")
			if SetCarrierFrequency(rdr,frequencie,P=P)!=0:
				if P:print(f'使用AA27配置单频点{frequencie}kHz失败')
				return -1
		
		# 获取并验证跳频表是否是单频点
		frequencies = GetFreqHopTable(rdr, P=False)
		if frequencies is None:
			if P: print("获取单频点跳频表失败")
			return -1
		
		if P: print(f'单频点跳频表:{frequencies}')
		
		# 验证是否是单频点
		if frequencies==[frequencie]:
			if P:print("验证成功：跳频表是期望的单频点")
			return 0
		if P:print(f"验证失败：期望单频点{frequencie}，实际跳频表为{frequencies}")
		return -1

if __name__=='__main__':
	# main_dir=os.path.dirname(sys.argv[0])+'\\'
	# files=sorted(os.listdir(main_dir))
	#以上是旧写法，以下是新写法
	# main_file_info=get_main_file_info()
	# main_dir=main_file_info["main_dir"]#（如 C:\test）
	# main_filename=main_file_info["main_filename"]#（如 main.py / main.exe）
	# main_full_path=main_file_info["main_full_path"]#（如 C:\test\main.py）
	# print("main_file_info:",main_file_info)
	while True:
		rdr=Create(input("请输入读写器地址(可留空自动搜索):"))
		# rdr=Create("COM4")
		# rdr=Create("192.168.1.160")
		# rdr=Create("USB")
		if not rdr:print();continue
		print("模块名称:"+GetModuleName(rdr,P=True))
		print("模块序列号:"+GetModuleSerialNumber(rdr,P=True))
		SwitchToBOOTLayer(rdr,P=True)
		print("模块名称:"+GetModuleName(rdr,P=True))
		print("模块序列号:"+GetModuleSerialNumber(rdr,P=True))
		SwitchToAPPLayer(rdr,P=True)
		print("模块名称:"+GetModuleName(rdr,P=True))
		print("模块序列号:"+GetModuleSerialNumber(rdr,P=True))
		ConnectionName=GetConnectionName(rdr)
		rdr.close()
		print('已断开'+ConnectionName+'的连接\n')
