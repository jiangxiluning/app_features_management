// 密码哈希函数（使用 SHA-256 哈希）
async function encryptPassword(password) {
    // 使用简单的 SHA-256 哈希实现
    function sha256(input) {
        const chars = '0123456789abcdef';
        const K = [
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
            0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
            0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
            0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
            0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
            0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
            0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
            0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
            0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
            0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
            0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
            0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
            0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
            0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
            0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
            0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
        ];
        
        function rotateRight(n, bits) {
            return (n >>> bits) | (n << (32 - bits));
        }
        
        function choice(x, y, z) {
            return (x & y) ^ (~x & z);
        }
        
        function majority(x, y, z) {
            return (x & y) ^ (x & z) ^ (y & z);
        }
        
        function sigma0(x) {
            return rotateRight(x, 2) ^ rotateRight(x, 13) ^ rotateRight(x, 22);
        }
        
        function sigma1(x) {
            return rotateRight(x, 6) ^ rotateRight(x, 11) ^ rotateRight(x, 25);
        }
        
        function gamma0(x) {
            return rotateRight(x, 7) ^ rotateRight(x, 18) ^ (x >>> 3);
        }
        
        function gamma1(x) {
            return rotateRight(x, 17) ^ rotateRight(x, 19) ^ (x >>> 10);
        }
        
        function padMessage(message) {
            const messageLength = message.length * 8;
            const paddingLength = (512 - (messageLength + 64) % 512) % 512;
            const paddedMessage = new Uint8Array((messageLength + paddingLength + 64) / 8);
            // 模拟 TextEncoder().encode(message)
            for (let i = 0; i < message.length; i++) {
                paddedMessage[i] = message.charCodeAt(i);
            }
            paddedMessage[message.length] = 0x80;
            for (let i = 0; i < 8; i++) {
                paddedMessage[paddedMessage.length - 8 + i] = (messageLength >> (56 - i * 8)) & 0xff;
            }
            return paddedMessage;
        }
        
        function processMessage(paddedMessage) {
            const blocks = [];
            for (let i = 0; i < paddedMessage.length; i += 64) {
                const block = new Uint32Array(16);
                for (let j = 0; j < 16; j++) {
                    block[j] = (
                        paddedMessage[i + j * 4] << 24 |
                        paddedMessage[i + j * 4 + 1] << 16 |
                        paddedMessage[i + j * 4 + 2] << 8 |
                        paddedMessage[i + j * 4 + 3]
                    ) >>> 0;
                }
                blocks.push(block);
            }
            
            let H0 = 0x6a09e667;
            let H1 = 0xbb67ae85;
            let H2 = 0x3c6ef372;
            let H3 = 0xa54ff53a;
            let H4 = 0x510e527f;
            let H5 = 0x9b05688c;
            let H6 = 0x1f83d9ab;
            let H7 = 0x5be0cd19;
            
            for (const block of blocks) {
                const W = new Uint32Array(64);
                for (let t = 0; t < 16; t++) {
                    W[t] = block[t];
                }
                for (let t = 16; t < 64; t++) {
                    W[t] = (gamma1(W[t - 2]) + W[t - 7] + gamma0(W[t - 15]) + W[t - 16]) >>> 0;
                }
                
                let a = H0;
                let b = H1;
                let c = H2;
                let d = H3;
                let e = H4;
                let f = H5;
                let g = H6;
                let h = H7;
                
                for (let t = 0; t < 64; t++) {
                    const T1 = (h + sigma1(e) + choice(e, f, g) + K[t] + W[t]) >>> 0;
                    const T2 = (sigma0(a) + majority(a, b, c)) >>> 0;
                    h = g;
                    g = f;
                    f = e;
                    e = (d + T1) >>> 0;
                    d = c;
                    c = b;
                    b = a;
                    a = (T1 + T2) >>> 0;
                }
                
                H0 = (H0 + a) >>> 0;
                H1 = (H1 + b) >>> 0;
                H2 = (H2 + c) >>> 0;
                H3 = (H3 + d) >>> 0;
                H4 = (H4 + e) >>> 0;
                H5 = (H5 + f) >>> 0;
                H6 = (H6 + g) >>> 0;
                H7 = (H7 + h) >>> 0;
            }
            
            let hash = '';
            for (const h of [H0, H1, H2, H3, H4, H5, H6, H7]) {
                for (let i = 3; i >= 0; i--) {
                    hash += chars[(h >> (i * 8)) & 0xf];
                    hash += chars[(h >> (i * 8 + 4)) & 0xf];
                }
            }
            return hash;
        }
        
        const paddedMessage = padMessage(input);
        return processMessage(paddedMessage);
    }
    
    try {
        // 使用自定义的 SHA-256 哈希实现
        const hashHex = sha256(password);
        // 返回哈希后的密码
        return {
            password: hashHex,
            salt: ''
        };
    } catch (error) {
        console.error('密码哈希失败:', error);
        // 发生错误时，返回密码本身
        return {
            password: password,
            salt: ''
        };
    }
}

// 测试密码哈希函数
async function testHash() {
    const password = 'admin123';
    const result = await encryptPassword(password);
    console.log('密码:', password);
    console.log('哈希值:', result.password);
}

testHash();