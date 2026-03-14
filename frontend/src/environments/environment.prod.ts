export const environment = {
  production: true,
  apiUrl: '',
  wsUrl: (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host + '/ws/chat'
};
