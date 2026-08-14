import { Message } from '../store';

export const processUploadedFiles = async (files: FileList | File[]): Promise<{ context: string; errors: string[] }> => {
  const result: { context: string; errors: string[] } = { context: '', errors: [] };
  if (!files || files.length === 0) return result;
  
  // Just mock file processing for now to keep it simple
  const fileNames = Array.from(files).map(f => f.name).join(', ');
  result.context = `[Attached files: ${fileNames}]`;
  return result;
};

export const parseSSEStream = async (
  reader: ReadableStreamDefaultReader<Uint8Array>,
  setStreamingMessage: (msg: string) => void,
  onMeta?: (meta: any) => void
): Promise<string> => {
  const decoder = new TextDecoder();
  let fullResponse = '';
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    
    for (const line of lines) {
      if (line.trim() === '') continue;
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') continue;
        try {
          const parsed = JSON.parse(data);
          if (parsed.content) {
            fullResponse += parsed.content;
            setStreamingMessage(fullResponse);
          } else if (parsed.text) {
            fullResponse += parsed.text;
            setStreamingMessage(fullResponse);
          }
          if (parsed.meta && onMeta) {
            onMeta(parsed.meta);
          }
        } catch (e) {
          // Ignore invalid JSON in stream
        }
      }
    }
  }
  return fullResponse;
};

export const parseJSONResponse = async (
  reader: ReadableStreamDefaultReader<Uint8Array>,
  setStreamingMessage: (msg: string) => void,
  onMeta?: (meta: any) => void
): Promise<string> => {
  const decoder = new TextDecoder();
  let fullResponse = '';
  
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    fullResponse += decoder.decode(value, { stream: true });
  }
  
  try {
    const parsed = JSON.parse(fullResponse);
    if (parsed.content) {
      setStreamingMessage(parsed.content);
      if (parsed.meta && onMeta) onMeta(parsed.meta);
      return parsed.content;
    }
    if (parsed.answer) {
       setStreamingMessage(parsed.answer);
       if (parsed.meta && onMeta) onMeta(parsed.meta);
       return parsed.answer;
    }
    if (parsed.response) {
       setStreamingMessage(parsed.response);
       if (parsed.meta && onMeta) onMeta(parsed.meta);
       return parsed.response;
    }
  } catch (e) {
    console.error("Failed to parse JSON response");
  }
  return fullResponse;
};

export const createUserMessage = (convId: string, content: string, files?: File[]): Message => {
  return {
    id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
    conversationId: convId,
    role: 'user',
    content,
    timestamp: new Date().toISOString(),
    attachments: files ? Array.from(files).map(f => ({ name: f.name, url: '', type: f.type, size: f.size })) : undefined,
  };
};

export const createAssistantMessage = (convId: string, content: string, isError: boolean, meta: any): Message => {
  return {
    id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
    conversationId: convId,
    role: 'assistant',
    content,
    timestamp: new Date().toISOString(),
    isError,
    citations: meta?.citations,
    modelUsed: meta?.modelUsed || meta?.model,
    latencyMs: meta?.latencyMs,
    tokenCount: meta?.tokenCount,
  };
};

export const createErrorMessage = (convId: string): Message => {
  return {
    id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
    conversationId: convId,
    role: 'assistant',
    content: 'Error: Could not connect to the server.',
    timestamp: new Date().toISOString(),
    isError: true,
  };
};

export const buildChatHeaders = (accessToken?: string) => {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  return headers;
};

export const buildChatRequestBody = ({ message, conversationId, history, language, isAuthenticated }: any) => {
  return JSON.stringify({
    message,
    conversation_id: conversationId,
    history,
    language,
    stream: isAuthenticated,
  });
};

export const buildConversationHistory = (messages: Message[]) => {
  return messages.map((m) => ({ role: m.role, content: m.content }));
};

export const getChatEndpoint = (isAuthenticated: boolean) => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
  if (!isAuthenticated) {
    return `${baseUrl}/api/v2/chat/guest`;
  }
  return `${baseUrl}/api/v2/chat/stream`;
};

export const getResponseLanguage = (language: string | undefined, selectedLanguage: string) => {
  return language || (selectedLanguage === 'auto' ? 'en' : selectedLanguage);
};
