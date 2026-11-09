/* Inspect or repair unsigned embedded AVB boot descriptor in a scratch file.
 * - If no AVBf footer is present, or AVB0 algorithm_type != 0 (signed AVB),
 *   exits 0 without opening for write (unless --require-repair is passed).
 * - If an AVBf footer with unsigned AVB0 (algorithm_type == 0) is present,
 *   validates bounds/descriptors and updates image_size + sha256 digest in-place.
 * - Any malformed AVBf/unsigned-AVB0 or I/O failure returns non-zero so the
 *   installer aborts before touching the boot partition.
 */
#define _FILE_OFFSET_BITS 64
#define _POSIX_C_SOURCE 200809L
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <errno.h>

#define LIMIT (512ULL*1024*1024)
static uint32_t u32(const unsigned char *p) { return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3]; }
static uint64_t u64(const unsigned char *p) { return (uint64_t)u32(p)<<32 | u32(p+4); }
static void set64(unsigned char *p,uint64_t n) { for (int i=7;i>=0;--i) { p[i]=n; n>>=8; } }
static int readat(int fd,void *data,size_t n,uint64_t off) {
    unsigned char *p=data; while(n) { ssize_t z=pread(fd,p,n,(off_t)off); if(z<=0)return -1; p+=z;off+=z;n-=z; } return 0;
}
static int writeat(int fd,const void *data,size_t n,uint64_t off) {
    const unsigned char *p=data; while(n) { ssize_t z=pwrite(fd,p,n,(off_t)off); if(z<=0)return -1; p+=z;off+=z;n-=z; } return 0;
}
static int writeall(int fd,const void *data,size_t n) {
    const unsigned char *p=data; while(n) { ssize_t z=write(fd,p,n); if(z<0&&errno==EINTR)continue; if(z<=0)return -1;p+=z;n-=z;} return 0;
}
static int val(char c) { if(c>='0'&&c<='9')return c-'0'; if(c>='a'&&c<='f')return c-'a'+10; return -1; }
static int hash_with_busybox(int image,const char *bb,const unsigned char *salt,size_t sn,uint64_t size,unsigned char out[32]) {
    int in[2],outpipe[2],status; pid_t pid;
    if(pipe(in)||pipe(outpipe))return -1;
    pid=fork(); if(pid<0)return -1;
    if(!pid) { dup2(in[0],0);dup2(outpipe[1],1);close(in[0]);close(in[1]);close(outpipe[0]);close(outpipe[1]);execl(bb,bb,"sha256sum",(char *)NULL);_exit(127); }
    close(in[0]);close(outpipe[1]); signal(SIGPIPE,SIG_IGN);
    int err=writeall(in[1],salt,sn);unsigned char buf[65536]; uint64_t off=0;
    while(!err && off<size) {size_t n=size-off>sizeof(buf)?sizeof(buf):(size_t)(size-off);if(readat(image,buf,n,off)||writeall(in[1],buf,n)){err=-1;break;}off+=n;}
    close(in[1]); char text[96];size_t got=0;while(got<sizeof(text)){ssize_t n=read(outpipe[0],text+got,sizeof(text)-got);if(n<0&&errno==EINTR)continue;if(n<=0)break;got+=(size_t)n;}close(outpipe[0]);
    if(waitpid(pid,&status,0)!=pid||!WIFEXITED(status)||WEXITSTATUS(status)!=0||got<64)err=-1;
    for(int i=0;i<32&&!err;i++){int a=val(text[2*i]),b=val(text[2*i+1]);if(a<0||b<0)err=-1;else out[i]=(unsigned char)((a<<4)|b);}
    return err;
}
int main(int argc,char **argv) {
    int fd=-1,rc=1,require_repair=1; struct stat st;
    unsigned char footer[64],header[256],desc[132],digest[32],sizebe[8],*salt=NULL;
    uint64_t size,original,voff,vsize,auth,aux,doff,dlen,pos,end,match=0,mdigest=0,mlength=0; uint32_t saltlen=0,algo=0;
    const char *imgpath=NULL,*bbpath=NULL;
    if(argc==3) { imgpath=argv[1]; bbpath=argv[2]; require_repair=1; }
    else if(argc==4 && !strcmp(argv[1],"--if-unsigned")) { imgpath=argv[2]; bbpath=argv[3]; require_repair=0; }
    else { fprintf(stderr,"usage: fix_avb [--if-unsigned] scratch-image busybox\n"); return 2; }

    fd=open(imgpath,O_RDONLY|O_NOFOLLOW);
    if(fd<0||fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_nlink!=1||st.st_size<320||(uint64_t)st.st_size>LIMIT)goto done;
    size=(uint64_t)st.st_size;
    if(readat(fd,footer,64,size-64))goto done;
    if(memcmp(footer,"AVBf",4)) {
        if(!require_repair){close(fd);return 0;}
        goto done;
    }
    if(u32(footer+4)!=1)goto done;
    original=u64(footer+12);voff=u64(footer+20);vsize=u64(footer+28);
    if(!original||original>voff||voff>size-64||vsize<256||vsize>4*1024*1024||vsize>size-64-voff)goto done;
    if(readat(fd,header,256,voff)||memcmp(header,"AVB0",4))goto done;
    algo=u32(header+28);
    if(algo!=0) {
        if(!require_repair){close(fd);return 0;}
        goto done;
    }
    close(fd); fd=-1;
    fd=open(imgpath,O_RDWR|O_NOFOLLOW);
    if(fd<0||fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_nlink!=1||(uint64_t)st.st_size!=size)goto done;
    auth=u64(header+12);aux=u64(header+20);doff=u64(header+96);dlen=u64(header+104);
    if(auth!=0||aux!=vsize-256||doff>aux||dlen>aux-doff)goto done;
    pos=voff+256+doff;end=pos+dlen;
    while(pos<end) {
        if(end-pos<16||readat(fd,desc,16,pos))goto done;
        uint64_t tag=u64(desc), n=u64(desc+8); if(n%8||n>end-pos-16)goto done;
        if(tag==2) {
            if(n+16<132||readat(fd,desc,132,pos))goto done;
            uint32_t nl=u32(desc+56),sl=u32(desc+60),dl=u32(desc+64),flags=u32(desc+68);
            uint64_t variables=(uint64_t)nl+sl+dl;
            if(variables>n+16-132 || ((116+variables+7)&~7ULL)!=n)goto done;
            if(nl==4) {
                unsigned char name[4]; if(readat(fd,name,4,pos+132))goto done;
                if(!memcmp(name,"boot",4)) {
                    if(match||memcmp(desc+24,"sha256",6)||desc[30]!=0||dl!=32||sl>4096||flags!=0)goto done;
                    match=pos;mdigest=pos+132+nl+sl;mlength=pos+16;saltlen=sl;
                }
            }
        }
        pos+=16+n;
    }
    if(pos!=end||!match)goto done;
    salt=malloc(saltlen?saltlen:1);if(!salt||readat(fd,salt,saltlen,match+132+4))goto done;
    if(hash_with_busybox(fd,bbpath,salt,saltlen,original,digest))goto done;
    set64(sizebe,original);
    if(writeat(fd,sizebe,8,mlength)||writeat(fd,digest,32,mdigest)||fsync(fd))goto done;
    fprintf(stderr,"Unsigned embedded AVB boot hash repaired.\n");rc=0;
done:
    if(rc)fprintf(stderr,"Refused AVB repair: unexpected image or I/O error; boot was not flashed.\n");
    free(salt);if(fd>=0)close(fd);return rc;
}
