const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const config = getDefaultConfig(__dirname);

// 只监听 mobile 自身和 shared 目录（法规/规则数据）
config.watchFolders = [
  path.resolve(__dirname),
  path.resolve(__dirname, '../shared'),
];

// Resolve node_modules from mobile directory
config.resolver.nodeModulesPaths = [
  path.resolve(__dirname, 'node_modules'),
];

module.exports = config;
