import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.studyquest.app',
  appName: 'Study Quest',
  webDir: 'www',
  server: {
    cleartext: false,
    allowNavigation: ['study-quest-2t6s.onrender.com']
  },
  plugins: {
    LocalNotifications: {
      smallIcon: 'ic_stat_icon_config_sample',
      iconColor: '#FF5A00'
    }
  },
  android: {
    allowMixedContent: false
  }
};
export default config;