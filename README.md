# Sbackup: 一个可以帮你备份文件夹的工具.

## Q: Sbackup是什么？

Sbackup是一个工具，可以帮助用户备份文件夹，目前仅支持命令行调用，UI正在开发中......

## Q: Sbackup有什么优势？

Sbackup体积小，启动速度超快，占用极低.

## 使用教程

### 安装方法

下载最新版的Sbackup，并把Sbackup.exe放在已经添加了环境变量的目录下面.

### 使用方法

```powershell
Sbackup [args]
```

#### 添加备份策略

```powershell
Sbackup add folder_path
```

folder_path: 被备份的文件夹路径.

#### 删除备份策略

```powershell
Sbackup remove
```

或者:

```powershell
Sbackup rm
```

#### 查看所有备份策略

```powershell
Sbackup all
```

#### 备份文件夹

```powershell
Sbackup save
```

#### 查看版本信息

```powershell
Sbackup version
```

## 实现原理

Sbackup根据文件夹的最后修改日期决定是否备份.

## 储存方式

备份策略储存在与Sbackup.exe同一目录下的sbackup.json中，请不要轻易修改此文件，否则可能导致备份策略永久消失.

## 作者

[xiatianxuan (xiatianxuan) - Gitee.com](https://gitee.com/xiatianxuan)

[xiatianxuan个人主页](https://xnors-codeseed.pages.dev/)

### 声明：xiatiaxuan与CodeSeed为同一人.

## 特别鸣谢

[Xnors Studio](https://xnors.github.io/)

## 加入我们？

请发送邮件到：xiatianxuan2025@163.com
