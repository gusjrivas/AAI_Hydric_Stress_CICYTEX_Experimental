import ast
import base64
import bz2
import hashlib
import inspect
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_laya_runtime_deployment_metadata import CHECKPOINT_FILES

PLAN_SCHEMA = "laya-runtime-provenance-plan-v1"
EVIDENCE_SCHEMA = "laya-runtime-provenance-evidence-v1"
SOURCE_REPOSITORY = "https://github.com/NandhaKishorM/laya"
CHECKPOINT_REPOSITORY = "https://huggingface.co/convaiinnovations/laya"
SOURCE_COMMIT = "68804629e8ccd9d616d48a40e87de9fabbeae069"
CHECKPOINT_COMMIT = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"
CHECKPOINT_README_FRONTMATTER = (
    b"---\nlicense: apache-2.0\nlibrary_name: transformers\n"
    b"pipeline_tag: text-classification\n"
    b"tags: [laya, system-one, calibrated-decisions, rlcd, classification, routing, "
    b"scoring, guardrails, moderation, reinforcement-learning, commercial-use]\n---\n"
)
APACHE_2_LICENSE_B85 = b"".join(
    (
        b"LRx4!F+o`-Q(3O-E0h2MvwwgQ5Cno!XaD#=|KFfL|Nrn{5FdAL3@A`RF1w!f!AUMN*IQ(PN(dCF*lEdzz`zEY2o&_uG-#ttru85)",
        b"VjicdfQ<n405s4L5;Txy00w{n0000QX%Rg}fQ$f|V1pAw0hDQg69P>nh{|ZxXwsT`2=yMI000001B{t6VlglRWWh23Xu>cAFbNR?",
        b"0yHLw(^PtC4^YT@o}kcV4@faA0t0L?Jzv2`=x8{|M>qAg^?bjt+c>AY6j!98Lyqms5P4AX>gg;h8XL{|-Yj!oS8OmeN`d$tz%^Lo",
        b"yIdW=>)iWgRJOH1ThmnAB$a8*Y%+<tlkCsk;zWAE0uvGtG>rJqT=nTn9Oj*)A9eF4@Gj5sz`u7^H{<UV-Y+Y*7h?qkH0=;AcFu{k",
        b"AfBASjp4!*%-i*Z#Os&@p(Kt$R~Yd<v{7~n$5WoC3Bx*8^h(?ZO}J5#q<nl%)j*n(KnTmcE3g{A9G#Ol;AzW3OkTskhEt?24`5aY",
        b"ImMoe8z_fY7pp@GU@FSSjogn$d-bSw5P~cSWn9e2afvkePG;?Pv}#ptN099n!;K{|!0Aa*mbX{6gpExd&PI`HZ7eAV`^@KHXa*pH",
        b"PgYbG>yy`{8%F@M4c^n6NdcA_a5D-;>Kg`#?<h0UV@w;F$PGj;GtO5%2^U)(i`}4w0~o9HT?|(iTuS6+yV+1iF>0e#UaI_Eo!N=Z",
        b"gV+|yq?S)CK1M@{zM7a`9mE!ZXD@Sz3qeI5fpdP;fyHK?Ohgr0hrEXjQLl-!j<bwMYOd6PPep1QpW_Y~*?R=YLEE&+L#0!#t?rQx",
        b"JkG$jj;xI2sFc0OE7P1MQ70-maoI56+tcA)oUl_tOqp%a<=lG?;tp7#<w1)mq#OAv(ViS(k$0sL=Xe=~aBWMd!pl@GlxVT-9h<@*",
        b"c<NO2#Ig;b*A>Asu2)JYj(nk-QgJ~=U0fIg7pUOD7_@P`2TG1>H=#!Ovk3BZ!l5Z@>(>_E3C)J=^%2_q%nrK5CPiwx!>E9Vj`78_",
        b"Tq6|Yjvp-&tTf9?)wOeI4}j=rsU0&F%D^d%ELs(Tz-HbTClPQ9g}Xzo8zH6uz^n;Pm<7mJw*sQ;iHFI+gkxqN4K%2H3ve|XfwvWz",
        b"8?LoD6HP0uwQR~xcNDedZFG+>DT`2NnX<0*i(js~`68C3aId?MH|gdGK>(B5R1yI|Du%f4<<mI+i0xYV{zleB^p@MyJaK)Uybws_",
        b"(2FVhWy`bZ@QdEFOA&5zjw<;yrg}|N%SU8eT3Nl7@tpS6#1I&WC)~4)EVNODt(lbqCzDc7L3T&*Tkkf`JYKlQMaNC^dD&Adty!Rh",
        b"2hHaC^o~BSU2Pukwa2!ZdyL0iwioEq^mSvqFFk%=FhWPPps?EN11^-+jdt_nhxy^Ch_<3fVsc`nW0;}>RE#JIPD(x`AaWD-37_CU",
        b"ckjsY8D0RmD5VJ&g_?jj_x~?MS6}7bs(-F_M{07F(TTAgnoWc=-t{^z>X&4)i3v`TDAu%!9o@*Ow>|I^!R$rW`EjA5?)%FO@nJgh",
        b"4&`%Q1!^7afN)Z1D0&IEj<AwPEuMPu&OOxs51K`Sg2Tm<9lYr#nKXbT06z$_quiu6OFe!V9*8&yR_GUomp)L2kOKapmTll_8Qnkb",
        b"bIdOx_)2)t;PD^l8m=Xh-{a(rYCzf(ytrSy=!su#I<_7Vp%*ieE{sj4>d_4;GdWGpz#sN*#4n2ouY5kPsQxa2<r|`D^s()9cv|SV",
        b"*TYzbW#3{`u!0)x!PCQeB&Up%A2%^c)~-EQ#|)x~D#qp8%t1Q`6(C!gtbw%rvZ@yUA-2_~ec$D;5!o7HlR`>6LsCFz(n;tgK+ax+",
        b"Fi0~0LouMM)&d+k&WRwOLzqe~)2pyF!AQ)g&w*7KwRF!DQn!qIGBA;&V@$as-N;AbNk&bFeB_=U1%il_-LpFf8+7ZwL5QpGDMg7C",
        b"j3WCisDlNF+F+XwA~`ZMxSHXMJzQ&gOq4{kYlT(~YXYUDi#%2^BFHB<3W^It3k`TiNT{+=4QU19aVEL(G4zMJo~%Az)a!Mf*&sW@",
        b"0pSb`Tg#6Jv4K@V+ax|OP7uwR8Xud0?FyAuEV2VB15DRjN|i*gglBXVtVCT?x>lnu1@AglMmQAgHwqnpJq`l{0;NR)fl3*^fwrK$",
        b";ImxmN&A}y(+m9<JoxJQ=;8hxQkjpN%4U3Amcc68ovDhWu=MKzrcswoPuJ_8%|Uq$hTf^@?gH>&O#@(fdWu&9QlWI=rv+fatQTgD",
        b"J$KH9_DKe=Cnz*)ej&Ga4<@I^hcu!*FdXby9f?ah*7lsHB)sc9F1xWlI@ff*uD?v@kes0tUjYV^N@+5$Bk#<Ub0IU9Ov|iG^lfo5",
        b"1%s9n<joPgg(rBF-m?US7*!6Vk&FRT+-uR7<oGx0{c@O|+2iey{9crD!ZD)>j0K&JT|87&x=`!Yppa`uklGd^F<nMVF^w2d5;5*G",
        b"6#`|HhTPn8k7Nm2jEGt@V0YK2e{~^M0aX?24=E*!I&kd>BP7I-KJpS#fO~Z)REa*_1EdnnO0`y$ERsI`4*sr-+B@Lt$2$<(NH`>S",
        b"Yq-6bu1smBHYCO(0P`zF=bibD8njy09tXf`1zD@9P}oaLa^!cF$(pdAXdL4vxX~T?lv%(rqqFgt8yLzA8=>i?{VE)qa^Vq30{h-q",
        b"PObHE5D@r-ZeKlYS_@I~@Y;Tt<9{Yd`<%J0_&Ri0IAF#m(|fT)KnnyxK=X%hLim&BolFRfVEi@cbVJv~#8BWdtf6zJj9CGzNZO`L",
        b"a|lhEy%s@RtF$!l5H`zDK_U*?no^YrI{?v!5_zv{I<f~Qh^WRvk@_1dwJoFb)6WRUB_=X73=Oi3ia_DI;L1sgO4E}y6_<uHBw4?%",
        b"WNDlfMr;@u5IdSn7^qICQim`Lu;;y-nCV<vu}fP%F%S^c8Mqrz^fW`ssbn#gl2Oggttk{~*eDm`wlRmvr(rOOMhgZ_7<9%Vj_84x",
        b"EUX(FCh2MvLhXgFT4sAH&0NhUnMC*?X$3P^1(P6!K?t%f5>Yoe&s(<if!V@EAu*;AqI7`G6zPUunZz_Bwn#xkcFWRps>=Rcb`6dI",
        b"@@Fh71LxQ_Vv-!lMJZ!QULsJKBFR`%;PG{#pO|7Hv?NTDp%+9fns3E11R1X*y+gX@BeGf2=sC1D2WCUmz)-}BV5!GI_tbC7Wrvq)",
        b"f!lvs)#lYomPj4M(gyG~@>J?zY7tY^G#|MLX?blMVhXevRAKnq7R_otL*ehf`G{9-Hg0V$3aXPfu-0oY%;ulbHmQ?BCU-qL{3)Hz",
        b"XQ$;tX^F8mfw2tCOS?EKv8eoHm+FA>?&31|w2ikK2LdPl0DSE$Z8C$g`j9`Hb*7#3LB9V~77;`7Bd^2Vj|Fh^kd2vCOwW&n#IMh;",
        b"ZWg1`s#r`bDhLwG1uk599Pef^>Vd`+*@Vr4Y8|XACALF`1rjKU1+=hYMS`@Y6(xvNEu#=Ytc{?~4^&zA+4~QS?!-6UIvra=Fylnl",
        b"si(qGHUo91Pn>6#ZYm>rLt%*^a|Ip9GqQH`*(4oAVyfB?KcG2~HYA!sKp2u16_c4bhe%pH_V?ru1EIm*9Kp`!S*XT>S$VQt?{42j",
        b"5=4dfrNhD?^1RBV_|Oo_WyDh}C@P|siD@uinM5IJQBa|&QDtPns*uf8!9`LjL!ovPJ|=4GZ9`)UwA(uBis`CZbFPyQ2Bqd@%xr6m",
        b"jfJUXJ7<S%oeyQ-(>a{NVMqnhGI5E|M`$J(+}eah%ev5@h%|9y0h<Qx1}G6Q=B$Ssae(#rF=F+UDR8v-#55gP8~E}fLoV!j)0}Ym",
        b"aFryzsCO$h#Y5IYbg5d2n0TN=ysA?sHpf1e<0~bQR9+oM;z0(m%p}t(bK+4<Hz<o@P7V&rs}8ishHrArm^}+*)>}F0PcH^cXHXb>",
        b"SVe?V2buzqP(}+Nq&se#SwjIPNZ4v1Zw6{FO`tYw#JqRU4fov2s}?Gz?4fflXqhlE(3RCFE~zb7U4(|D2RM=(i4Bd&YcGx5Lw9gA",
        b">RCz%ggTd|J?%|X8C4d5*pt<~CC!<Xg$(2{hqZuS^|@bZzXU+4F#|?G5vSl})T-$m2HOkRpIobA1bWylcSU+(HesrTtB^lAY-zKj",
        b"Qu3UUC<3vv5HXO>p_$ftR0vOtE0g7(K_@R6P|<}$F-;gYsxexkASlK##y$FI0fT|<8}_F43I=K-(O8lRq>)CZM<lk!ri+-#3plLW",
        b"&T7el-GtiJQCBRgv>@EB#N;EfssF{?kxmpOE4s?%00",
    )
)
CHECKPOINT_COMMIT_B85 = b"".join(
    (
        b"LRx4!F+o`-Q(22*kKh0T4&Q)a5I_(A_kaKY@W226@IV6m?rp~#Zq>IDRPtn=DY9mQFiDa63T;i3C#5|xGen-CG!az&O;1f3kp@ph",
        b"XwOu|JepxlOvn>45Ys^wP2y?~CZ<h1Q__t+GA7h|nV``$+fzs}7(mrcp`g_^m}*Z+r;|-a)ND+rk*S(#7-^}aO$!A8M10AN__+1T",
        b"#CoSmrk!jcM?xP6Y=mw^bhMYcA$yVnMyelaLB}j>r?UurmANjul&h?j(EOlYgeo$hAngY;_>m?XEfzrs5Cou*LNry+)^c>@&A5#`",
        b"rRn@g0u?*u7~kzdR+LlOA_RCg7ZS<>q%WAI-a<vv1$<t-vB89M)%=slt*XQPr5-n5bmMB^+iUFpKD^Go^2xNAMUbgJSe~?-3(TxC",
        b"P8#AS92aAOetI!ymqIG3?86rZX*QPHDQwW~pVK3BVP^^W_4L`;cpB3UdO_DSRlq(tpQ^AhqL?^mwO+wjw2)lj7q6Cf`RvYoZvI=-",
        b"eQ--4U}eVM?d4P)(v5i6FN{L(BG*G!$&it-rE^l=vtrv)Fa{X5!vn*kZBMI%1ZUTdleSO;1x;ECw&<-(tGq&#ao>7ID`zWUQE;Xw",
        b"(CpE=PoHuSadQ&6P6~Ptn{NtRL5ZPh6g8D|2~uqzdGlYvP|QAFDtoBnkhJpDxwQ&YBBOvhEzSf$c)|}br=2%w8<E$Mc^B){<w6yu",
        b"U_-g<iJivW*k9(|iQRraRTdyo0f{A;Et#LF9aR7`XzI6_H*##)cbK27cD@=*0=!KlbnGOhY-hQ@V(+r9N)XVp0-<IcwKgHpi7}cN",
        b">JvzCWPxTC3@D}Vlg;RupPP4!r|^y;((#k-OS8~n%0$6&D<O74wg1;*>!?>xTe1-=9^CoSOQ_b_%maOsI+venWD-Ciq+r|f`&$G|",
        b"O*CXP&K+D?m~KZVtoq^)T(#I)nssoDE+(S7VCS61aJjQl$|*H=!m?HwR!e;26!*m}@5kQ~@8~B9*&d5?#_);4O&VR8>KxJ(NBrhk",
        b"Ss?>jX&`Zzx*77z<i&c8D`>kqbC+Boh9xda8w)5v+sDB5K%LO5cH!W##=7BQSun9=>wr6yHH(eL%1{?ZDtR|Cu^1{S5cjo^NxZ}D",
        b"qO~yZhrrwNPrITf3q)r63f+T#X8_aB8y(Bo)F+1b4xr0eafB$joyifVajVgOKI;!TB(<-k@F&UQmmqX8!+!~)M{S_kHyDziZL+g8",
        b"P%6%JQs9iIBe3>t9GqTJn^0ZZ#fk-QZK?I)g*Mk;{9VZu;X*<!ia&q",
    )
)
EXPECTED_OBJECTS = (
    (
        "source_tag",
        "tag",
        "a0d473b307b7eaa7385ae04feea43c52581c4f5a",
        "7f7f43c230ac6e106c3cc3ee713b905964cd66cd8c4c91435f6441be0f8b91ed",
        912,
    ),
    (
        "source_commit",
        "commit",
        SOURCE_COMMIT,
        "f40967375c7dd748a8060268384ef4103830c19798b5954da485234ccc7cef7f",
        975,
    ),
    (
        "source_tree",
        "tree",
        "1f64e459fd2b9f55d7672b0457a2245faa49dce7",
        "da1be47947c251b312b4007946b4460dfca97ec3f5f88c9c2ba75203d976a218",
        1686,
    ),
    (
        "source_license",
        "blob",
        "d9a10c0d8e868ebf8da0b3dc95bb0be634c34bfe",
        "a6cba85bc92e0cff7a450b1d873c0eaa2e9fc96bf472df0247a26bec77bf3ff9",
        10173,
    ),
    (
        "source_pyproject",
        "blob",
        "4f05fe8dcd6c6e131c8200648e024d1bad7fc920",
        "375130a133e96f0c7481ed38f1cc59a86aea79a5dd984770215fecc8e1bedaa6",
        3956,
    ),
    (
        "checkpoint_commit",
        "commit",
        CHECKPOINT_COMMIT,
        "4e00a98879150b4c17b83ec48688c81e0b14a2b62ebf35b2c831ab67eb95fb75",
        1149,
    ),
    (
        "checkpoint_tree",
        "tree",
        "61ea5230f8c24a7b55f9b37e74518c6ef17e62b3",
        "0c4cc02bf64c39e2594beb5021c49193a857302c18d9f3aa121d67d179ee74d3",
        512,
    ),
    (
        "checkpoint_readme",
        "blob",
        "ac11a565c217959d0cb062748a2f83e05da446a5",
        "00355613796b3f5860b0d5b20392381d26580ec242e04a1fd150c7f116858602",
        23187,
    ),
    (
        "multilingual_tree",
        "tree",
        "de7883e4ef73e15f09af019dd10526bfd3099bcc",
        "23b429e24c9cc58fa0afe42aa15b91f45f02e463cec666dbe50e389d82189ea4",
        163,
    ),
    (
        "encoder_tree",
        "tree",
        "3dab0f21aa014e7aded1f8e8087665d2a501b457",
        "37615bcb694d28a74ad14f87e3969d1158c3c96e19365f59918331e3548517d0",
        39,
    ),
    (
        "tokenizer_tree",
        "tree",
        "fb46ae282300390f9b4441103b7186ec6694d59a",
        "b0956a8fbb7183c7270faf8491235ea8c33c9c104f54ac594c0ea72f500b341b",
        91,
    ),
    (
        "encoder_config",
        "blob",
        "0de0e2d30638873790cf962def52e2acf4db3eef",
        "83f6916d13ef0f556ac461f28308dc2bffa7ebeadee8ec9e2db5812020ea5bb4",
        1938,
    ),
    (
        "weights_lfs",
        "blob",
        "b99c8bea239c53f6f6bce734557dc6c403fa6b3e",
        "728656cf0aacad64dea942a0438242d8d5199db39e5602a77ebee6cd0319c759",
        134,
    ),
    (
        "laya_config",
        "blob",
        "00e35f88bb731bb9126a914666ab1cdac8a204c8",
        "25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6",
        472,
    ),
    (
        "tokenizer_lfs",
        "blob",
        "56d765858ed38eaabd35cd90759cbb1f89b0baa4",
        "9ca6155812f67a58160ce2cded92df5912c97509d38937ddc200f7fc8e142566",
        133,
    ),
    (
        "tokenizer_config",
        "blob",
        "c255ac0c8cb34a37d066cd0dafe313fd769d27ae",
        "6c6b2d8e3c84ce0e671c129cd6b374b235d6f9863042a5836358d00a89bbb5a1",
        524,
    ),
)


def _provenance():
    import human_feedback.runtime_provenance as provenance

    return provenance


def _git_sha1(kind: str, payload: bytes) -> str:
    return hashlib.sha1(
        kind.encode("ascii") + b" " + str(len(payload)).encode("ascii") + b"\0" + payload,
        usedforsecurity=False,
    ).hexdigest()


def _tree_entry(mode: str, path: str, object_id: str) -> bytes:
    return mode.encode("ascii") + b" " + path.encode("utf-8") + b"\0" + bytes.fromhex(object_id)


def _commit(tree: str = "1" * 40) -> bytes:
    return (
        f"tree {tree}\n"
        f"parent {'2' * 40}\n"
        "author Example <example@example.com> 1700000000 +0000\n"
        "committer Example <example@example.com> 1700000000 +0000\n"
        "\nrelease: 0.4.2\n"
    ).encode("ascii")


def _tag(commit: str = SOURCE_COMMIT) -> bytes:
    return (
        f"object {commit}\n"
        "type commit\n"
        "tag v0.4.2\n"
        "tagger Example <example@example.com> 1700000000 +0000\n"
        "\nlaya 0.4.2\n"
    ).encode("ascii")


def _private_error(exc: BaseException, *markers: str) -> None:
    rendered = "\n".join((str(exc), repr(exc), repr(exc.__cause__), repr(exc.__context__)))
    assert exc.__cause__ is None
    assert exc.__suppress_context__ is True
    assert all(marker not in rendered for marker in markers)


def _forge_exact(instance, **changes):
    forged = object.__new__(type(instance))
    for field in fields(instance):
        object.__setattr__(
            forged, field.name, changes.get(field.name, getattr(instance, field.name))
        )
    return forged


def _checkpoint_evidence(monkeypatch):
    from tests.test_laya_runtime_checkpoint import _legitimate_checkpoint_evidence

    return _legitimate_checkpoint_evidence(monkeypatch)


def _spec(provenance, role, repository, kind, payload):
    value = object.__new__(provenance.LayaGitObjectSpec)
    object.__setattr__(value, "role", role)
    object.__setattr__(value, "repository", repository)
    object.__setattr__(value, "kind", kind)
    object.__setattr__(value, "sha1", _git_sha1(kind, payload))
    object.__setattr__(value, "sha256", hashlib.sha256(payload).hexdigest())
    object.__setattr__(value, "size_bytes", len(payload))
    return value


def _synthetic_profile(monkeypatch, provenance, *, source_license=None, checkpoint_commit=None):
    checkpoint = _checkpoint_evidence(monkeypatch)
    small = {
        "encoder_config": b'{"model_type":"synthetic-laya"}\n',
        "laya_config": b'{"profile":"synthetic-laya"}\n',
        "tokenizer_config": b'{"tokenizer":"synthetic-laya"}\n',
    }
    payload_authority = {
        "weights": (hashlib.sha256(b"synthetic weights").hexdigest(), 17),
        "tokenizer": (hashlib.sha256(b"synthetic tokenizer").hexdigest(), 19),
    }
    lfs = {
        "weights_lfs": (
            b"version https://git-lfs.github.com/spec/v1\n"
            + f"oid sha256:{payload_authority['weights'][0]}\n".encode()
            + b"size 17\n"
        ),
        "tokenizer_lfs": (
            b"version https://git-lfs.github.com/spec/v1\n"
            + f"oid sha256:{payload_authority['tokenizer'][0]}\n".encode()
            + b"size 19\n"
        ),
    }
    if source_license is None:
        source_license = b"Apache License\nVersion 2.0, January 2004\n"
    source_pyproject = (
        b'[project]\nname = "laya"\nversion = "0.4.2"\n' b'license = { text = "Apache-2.0" }\n'
    )
    checkpoint_readme = CHECKPOINT_README_FRONTMATTER
    payloads = {
        "source_license": source_license,
        "source_pyproject": source_pyproject,
        "checkpoint_readme": checkpoint_readme,
        **small,
        **lfs,
    }

    def add_tree(role, entries):
        payloads[role] = b"".join(
            _tree_entry(mode, path, _git_sha1(kind, payloads[target]))
            for mode, path, kind, target in entries
        )

    add_tree("encoder_tree", (("100644", "config.json", "blob", "encoder_config"),))
    add_tree(
        "tokenizer_tree",
        (
            ("100644", "tokenizer.json", "blob", "tokenizer_lfs"),
            ("100644", "tokenizer_config.json", "blob", "tokenizer_config"),
        ),
    )
    add_tree(
        "multilingual_tree",
        (
            ("040000", "encoder", "tree", "encoder_tree"),
            ("100644", "model.safetensors", "blob", "weights_lfs"),
            ("100644", "rl_agent_config.json", "blob", "laya_config"),
            ("040000", "tokenizer", "tree", "tokenizer_tree"),
        ),
    )
    add_tree(
        "checkpoint_tree",
        (
            ("100644", "README.md", "blob", "checkpoint_readme"),
            ("040000", "multilingual", "tree", "multilingual_tree"),
        ),
    )
    add_tree(
        "source_tree",
        (
            ("100644", "LICENSE", "blob", "source_license"),
            ("100644", "pyproject.toml", "blob", "source_pyproject"),
        ),
    )
    payloads["source_commit"] = _commit(_git_sha1("tree", payloads["source_tree"]))
    payloads["source_tag"] = _tag(_git_sha1("commit", payloads["source_commit"]))
    if checkpoint_commit is None:
        checkpoint_commit = _commit(_git_sha1("tree", payloads["checkpoint_tree"]))
    payloads["checkpoint_commit"] = checkpoint_commit
    monkeypatch.setattr(provenance, "SOURCE_COMMIT", _git_sha1("commit", payloads["source_commit"]))
    monkeypatch.setattr(
        provenance,
        "CHECKPOINT_COMMIT",
        _git_sha1("commit", payloads["checkpoint_commit"]),
    )
    role_kind = {role: "tree" if role.endswith("_tree") else "blob" for role in payloads}
    role_kind.update(source_tag="tag", source_commit="commit", checkpoint_commit="commit")
    order = tuple(item[0] for item in EXPECTED_OBJECTS)
    objects = tuple(
        _spec(
            provenance,
            role,
            SOURCE_REPOSITORY if role.startswith("source_") else CHECKPOINT_REPOSITORY,
            role_kind[role],
            payloads[role],
        )
        for role in order
    )
    file_values = {
        "encoder_config": (
            hashlib.sha256(small["encoder_config"]).hexdigest(),
            len(small["encoder_config"]),
        ),
        "weights": payload_authority["weights"],
        "laya_config": (
            hashlib.sha256(small["laya_config"]).hexdigest(),
            len(small["laya_config"]),
        ),
        "tokenizer": payload_authority["tokenizer"],
        "tokenizer_config": (
            hashlib.sha256(small["tokenizer_config"]).hexdigest(),
            len(small["tokenizer_config"]),
        ),
    }
    fake_files = tuple(
        SimpleNamespace(
            role=item["role"],
            path=item["path"],
            sha256=file_values[item["role"]][0],
            size_bytes=file_values[item["role"]][1],
        )
        for item in CHECKPOINT_FILES
    )
    synthetic_checkpoint = object.__new__(type(checkpoint))
    object.__setattr__(synthetic_checkpoint, "plan", SimpleNamespace(files=fake_files))
    object.__setattr__(synthetic_checkpoint, "runtime_identity", checkpoint.runtime_identity)
    monkeypatch.setattr(provenance, "PROVENANCE_OBJECTS", objects)
    monkeypatch.setattr(provenance, "_deep_validate_checkpoint_evidence", lambda value: value)
    plan = provenance.prepare_laya_runtime_provenance_plan(synthetic_checkpoint)
    packets = tuple(
        (item.repository, item.kind, item.sha1, (payloads[item.role],)) for item in plan.objects
    )
    return plan, packets, payloads


def _rebind_synthetic_profile(monkeypatch, provenance, plan, payloads):
    rebound = tuple(
        _spec(
            provenance,
            item.role,
            item.repository,
            item.kind,
            payloads[item.role],
        )
        for item in plan.objects
    )
    monkeypatch.setattr(provenance, "PROVENANCE_OBJECTS", rebound)
    rebound_plan = _forge_exact(plan, objects=rebound)
    packets = tuple(
        (item.repository, item.kind, item.sha1, (payloads[item.role],)) for item in rebound
    )
    return rebound_plan, packets


def test_public_profile_constants_are_exact_closed_and_dual_digest_pinned():
    provenance = _provenance()
    assert provenance.PROVENANCE_PLAN_SCHEMA == PLAN_SCHEMA
    assert provenance.PROVENANCE_EVIDENCE_SCHEMA == EVIDENCE_SCHEMA
    assert provenance.SOURCE_REPOSITORY == SOURCE_REPOSITORY
    assert provenance.CHECKPOINT_REPOSITORY == CHECKPOINT_REPOSITORY
    assert provenance.SOURCE_COMMIT == SOURCE_COMMIT
    assert provenance.CHECKPOINT_COMMIT == CHECKPOINT_COMMIT
    assert provenance.MAX_PROVENANCE_OBJECTS == 16
    assert provenance.MAX_PROVENANCE_OBJECT_BYTES == 64 * 1024
    assert provenance.MAX_PROVENANCE_TOTAL_BYTES == 16 * 64 * 1024
    assert provenance.MAX_PROVENANCE_TREE_ENTRIES == 256
    assert provenance.MAX_PROVENANCE_PATH_COMPONENTS == 8
    assert provenance.MAX_PROVENANCE_DAG_VISITS == 64
    assert tuple(
        (
            item.role,
            item.repository,
            item.kind,
            item.sha1,
            item.sha256,
            item.size_bytes,
        )
        for item in provenance.PROVENANCE_OBJECTS
    ) == tuple(
        (
            role,
            SOURCE_REPOSITORY if role.startswith("source_") else CHECKPOINT_REPOSITORY,
            kind,
            sha1,
            sha256,
            size,
        )
        for role, kind, sha1, sha256, size in EXPECTED_OBJECTS
    )
    assert all(
        len(item.sha1) == 40
        and item.sha1 == item.sha1.lower()
        and int(item.sha1, 16) != 0
        and len(item.sha256) == 64
        and item.sha256 == item.sha256.lower()
        and int(item.sha256, 16) != 0
        for item in provenance.PROVENANCE_OBJECTS
    )


def test_plan_requires_exact_deeply_valid_pr34_evidence_before_object_consumption():
    provenance = _provenance()
    from human_feedback.runtime_checkpoint import LayaRuntimeCheckpointEvidence

    class Hostile:
        def __getattribute__(self, name):
            if name.startswith("__"):
                return object.__getattribute__(self, name)
            raise AssertionError("private-ancestor-marker")

    exact_but_unsealed = object.__new__(LayaRuntimeCheckpointEvidence)
    for invalid in (None, SimpleNamespace(), Hostile(), exact_but_unsealed):
        with pytest.raises((TypeError, ValueError)) as caught:
            provenance.prepare_laya_runtime_provenance_plan(invalid)
        _private_error(caught.value, "private-ancestor-marker")


def test_git_commit_parser_is_strict_closed_and_private():
    provenance = _provenance()
    parsed = provenance._parse_git_commit_bytes(_commit())
    assert parsed.tree_sha1 == "1" * 40
    assert parsed.parent_sha1s == ("2" * 40,)
    assert not hasattr(parsed, "raw_bytes")
    without_final_lf = provenance._parse_git_commit_bytes(_commit()[:-1])
    assert without_final_lf.tree_sha1 == parsed.tree_sha1
    assert without_final_lf.parent_sha1s == parsed.parent_sha1s
    header, _ = _commit().split(b"\n\n", 1)
    invalid = (
        _commit().replace(b"tree ", b"Tree ", 1),
        _commit().replace(b"tree " + b"1" * 40 + b"\n", b"", 1),
        _commit().replace(b"author ", b"author \xff", 1),
        _commit() + b"\0private-trailing",
        _commit().replace(b"\n\n", b"\ntree " + b"3" * 40 + b"\n\n", 1),
        _commit().replace(b"committer Example <example@example.com> 1700000000 +0000\n", b"", 1),
        header,
        header + b"\n\n",
    )
    for payload in invalid:
        with pytest.raises(ValueError) as caught:
            provenance._parse_git_commit_bytes(payload)
        _private_error(caught.value, "private-trailing")


def test_real_checkpoint_commit_without_final_lf_verifies_end_to_end(monkeypatch):
    provenance = _provenance()
    payload = bz2.decompress(base64.b85decode(CHECKPOINT_COMMIT_B85))
    assert len(payload) == 1149
    assert _git_sha1("commit", payload) == CHECKPOINT_COMMIT
    assert hashlib.sha256(payload).hexdigest() == (
        "4e00a98879150b4c17b83ec48688c81e0b14a2b62ebf35b2c831ab67eb95fb75"
    )
    assert payload.endswith(b"README: recommend max_len=8192, laya 0.3.20 notes")
    assert not payload.endswith(b"\n")

    parsed = provenance._parse_git_commit_bytes(payload)
    assert parsed.tree_sha1 == "61ea5230f8c24a7b55f9b37e74518c6ef17e62b3"
    assert parsed.parent_sha1s == ("d51a65072f7c8eab3c4186b6e062de63d0bd5303",)

    _, _, baseline_payloads = _synthetic_profile(monkeypatch, provenance)
    exact_plan, _, _ = _synthetic_profile(monkeypatch, provenance, checkpoint_commit=payload)
    exact_spec = next(item for item in exact_plan.objects if item.role == "checkpoint_commit")
    receipt = provenance._verify_laya_runtime_provenance_object_chunks(
        exact_plan, CHECKPOINT_COMMIT, iter((payload,))
    )
    assert receipt.spec is exact_spec
    assert receipt.provenance_object_verified is True

    synthetic_tree = _git_sha1("tree", baseline_payloads["checkpoint_tree"])
    aggregate_payload = payload.replace(
        b"tree 61ea5230f8c24a7b55f9b37e74518c6ef17e62b3",
        f"tree {synthetic_tree}".encode("ascii"),
        1,
    )
    aggregate_plan, aggregate_packets, _ = _synthetic_profile(
        monkeypatch, provenance, checkpoint_commit=aggregate_payload
    )
    assert not aggregate_payload.endswith(b"\n")
    assert provenance.verify_laya_runtime_provenance_objects(
        aggregate_plan, aggregate_packets
    ).receipts


def test_real_checkpoint_commit_still_rejects_ambiguous_or_truncated_bytes():
    provenance = _provenance()
    payload = bz2.decompress(base64.b85decode(CHECKPOINT_COMMIT_B85))
    header, _ = payload.split(b"\n\n", 1)
    invalid = (
        payload + b"\0private-trailing",
        payload.replace(b"\n", b"\r", 1),
        payload.replace(b"tree ", b"Tree ", 1),
        payload.replace(
            b"\n\n",
            b"\ntree 0000000000000000000000000000000000000000\n\n",
            1,
        ),
        header,
        header + b"\n\n",
        header + b"\n\n\n",
    )
    for corrupt in invalid:
        with pytest.raises(ValueError) as caught:
            provenance._parse_git_commit_bytes(corrupt)
        _private_error(caught.value, "private-trailing")


def test_annotated_tag_parser_requires_exact_commit_target_and_v042():
    provenance = _provenance()
    parsed = provenance._parse_git_tag_bytes(_tag())
    assert parsed.object_sha1 == SOURCE_COMMIT
    assert parsed.object_kind == "commit"
    assert parsed.tag == "v0.4.2"
    for payload in (
        _tag().replace(b"type commit", b"type tree"),
        _tag().replace(b"tag v0.4.2", b"tag 0.4.2"),
        _tag().replace(SOURCE_COMMIT.encode(), b"f" * 40),
        _tag() + b"private-trailing",
        _tag()[:-1],
    ):
        with pytest.raises(ValueError):
            provenance._parse_git_tag_bytes(payload)


def test_binary_tree_parser_preserves_order_and_rejects_unsafe_entries():
    provenance = _provenance()
    first = _tree_entry("100644", "LICENSE", "1" * 40)
    second = _tree_entry("040000", "multilingual", "2" * 40)
    parsed = provenance._parse_git_tree_bytes(first + second)
    assert tuple((item.mode, item.path, item.sha1) for item in parsed) == (
        ("100644", "LICENSE", "1" * 40),
        ("040000", "multilingual", "2" * 40),
    )
    invalid = (
        second + first,
        first + first,
        _tree_entry("120000", "link", "1" * 40),
        _tree_entry("160000", "submodule", "1" * 40),
        _tree_entry("100664", "weird", "1" * 40),
        _tree_entry("100644", "../escape", "1" * 40),
        _tree_entry("100644", "nested/path", "1" * 40),
        _tree_entry("100644", "C:private", "1" * 40),
        _tree_entry("100644", "back\\slash", "1" * 40),
        first[:-1],
        first + b"private-trailing",
    )
    for payload in invalid:
        with pytest.raises(ValueError) as caught:
            provenance._parse_git_tree_bytes(payload)
        _private_error(caught.value, "private-trailing", "C:private")


@pytest.mark.parametrize(
    ("payload", "expected_digest", "expected_size"),
    [
        (
            b"version https://git-lfs.github.com/spec/v1\n"
            b"oid sha256:9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204\n"
            b"size 643835514\n",
            "9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204",
            643835514,
        ),
        (
            b"version https://git-lfs.github.com/spec/v1\n"
            b"oid sha256:609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f\n"
            b"size 34363188\n",
            "609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f",
            34363188,
        ),
    ],
)
def test_large_checkpoint_blobs_are_exact_three_line_lfs_pointers(
    payload, expected_digest, expected_size
):
    parsed = _provenance()._parse_lfs_pointer_bytes(payload)
    assert parsed.sha256 == expected_digest
    assert parsed.size_bytes == expected_size
    for invalid in (
        payload.replace(b"\n", b"\r\n"),
        payload.rstrip(b"\n"),
        payload + b"extra\n",
        payload.replace(b"oid sha256:", b"oid sha1:"),
        payload.replace(str(expected_size).encode(), b"01"),
    ):
        with pytest.raises(ValueError):
            _provenance()._parse_lfs_pointer_bytes(invalid)


def test_license_and_package_declarations_are_exact_and_checkpoint_repo_is_not_alias():
    provenance = _provenance()
    assert CHECKPOINT_REPOSITORY != "https://huggingface.co/convaiinnovations/laya-multilingual"
    provenance._validate_source_license_bytes(b"Apache License\nVersion 2.0, January 2004\n")
    provenance._validate_source_pyproject_bytes(
        b'[project]\nname = "laya"\nversion = "0.4.2"\n' b'license = { text = "Apache-2.0" }\n'
    )
    provenance._validate_checkpoint_readme_bytes(CHECKPOINT_README_FRONTMATTER)
    invalid = (
        (provenance._validate_source_license_bytes, b"MIT License"),
        (
            provenance._validate_source_pyproject_bytes,
            b'[project]\nname="laya"\nversion="0.4.2"\nlicense="MIT"\n',
        ),
        (
            provenance._validate_checkpoint_readme_bytes,
            b"---\nlicense: apache-2.0\nlibrary_name: transformers\n"
            b"pipeline_tag: text-classification\n"
            b"tags: [laya-multilingual]\n---\n",
        ),
    )
    for validator, payload in invalid:
        with pytest.raises(ValueError):
            validator(payload)


def test_official_apache_license_object_is_accepted_but_near_miss_is_rejected(
    monkeypatch,
):
    provenance = _provenance()
    payload = bz2.decompress(base64.b85decode(APACHE_2_LICENSE_B85))
    assert len(payload) == 10173
    assert hashlib.sha256(payload).hexdigest() == (
        "a6cba85bc92e0cff7a450b1d873c0eaa2e9fc96bf472df0247a26bec77bf3ff9"
    )

    plan, packets, _ = _synthetic_profile(monkeypatch, provenance, source_license=payload)
    license_spec = next(item for item in plan.objects if item.role == "source_license")
    assert license_spec.size_bytes == 10173
    assert license_spec.sha256 == hashlib.sha256(payload).hexdigest()
    receipt = provenance._verify_laya_runtime_provenance_object_chunks(
        plan, license_spec.sha1, iter((payload,))
    )
    assert receipt.spec is license_spec
    assert receipt.provenance_object_verified is True
    assert provenance.verify_laya_runtime_provenance_objects(plan, packets).receipts

    near_miss = payload.replace(
        b"TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION",
        b"TERMS AND CONDITIONS FOR USE, REPRODUCTION, OR DISTRIBUTION",
        1,
    )
    with pytest.raises(ValueError):
        provenance._validate_source_license_bytes(near_miss)
    corrupted_packets = tuple(
        (
            repository,
            kind,
            sha1,
            (near_miss,) if sha1 == license_spec.sha1 else chunks,
        )
        for repository, kind, sha1, chunks in packets
    )
    with pytest.raises(ValueError):
        provenance.verify_laya_runtime_provenance_objects(plan, corrupted_packets)


def test_source_license_parser_accepts_only_canonical_newline_variants():
    provenance = _provenance()
    official = bz2.decompress(base64.b85decode(APACHE_2_LICENSE_B85))
    inherited_short = b"Apache License\nVersion 2.0, January 2004\n"

    provenance._source_license(official.replace(b"\n", b"\r\n"))
    provenance._source_license(official)
    provenance._source_license(inherited_short)

    invalid = (
        official.replace(b"\n", b"\r"),
        official.replace(b"\n", b"\r\n", 1),
        b"prefix\n" + official,
        official + b"suffix\n",
    )
    for payload in invalid:
        with pytest.raises(ValueError):
            provenance._source_license(payload)


def test_object_verifier_rejects_wrong_type_size_sha1_sha256_and_stream_shape():
    provenance = _provenance()
    bad_plan = SimpleNamespace()
    for value in (None, bad_plan, object()):
        with pytest.raises((TypeError, ValueError)):
            provenance._verify_laya_runtime_provenance_object_chunks(value, "1" * 40, iter((b"x",)))
    assert provenance.MAX_PROVENANCE_CHUNK_BYTES == provenance.MAX_PROVENANCE_OBJECT_BYTES
    assert provenance.MAX_PROVENANCE_CHUNKS == 64


def test_synthetic_exact_sixteen_object_dag_reaches_evidence_and_private_summary(
    monkeypatch,
):
    provenance = _provenance()
    plan, packets, _ = _synthetic_profile(monkeypatch, provenance)

    evidence = provenance.verify_laya_runtime_provenance_objects(plan, packets)

    assert type(evidence) is provenance.LayaRuntimeProvenanceEvidence
    assert evidence.plan is plan
    assert tuple(receipt.spec for receipt in evidence.receipts) == plan.objects
    assert len(evidence.receipts) == 16
    assert all(receipt.provenance_object_verified is True for receipt in evidence.receipts)
    assert evidence.source_git_content_verified is True
    assert evidence.checkpoint_git_content_verified is True
    assert evidence.source_license_declaration_observed is True
    assert evidence.checkpoint_license_declaration_observed is True
    true_flags = (
        "artifact_integrity_verified",
        "runtime_config_semantics_verified",
        "checkpoint_manifest_semantics_verified",
        "checkpoint_bytes_verified",
        "provenance_objects_verified",
        "source_git_content_verified",
        "checkpoint_git_content_verified",
        "source_license_declaration_observed",
        "checkpoint_license_declaration_observed",
    )
    false_flags = (
        "lock_verified",
        "sbom_verified",
        "lock_sbom_consistent",
        "oci_bytes_verified",
        "oci_manifest_semantics_verified",
        "origin_verified",
        "license_verified",
        "base_ancestry_verified",
        "runtime_materialized",
        "executor_available",
        "inference_executed",
    )
    assert all(getattr(evidence, name) is True for name in true_flags)
    assert all(getattr(evidence, name) is False for name in false_flags)
    for name in (*true_flags, *false_flags):
        forged = _forge_exact(
            evidence,
            **{name: False if name in true_flags else True},
        )
        with pytest.raises(ValueError):
            provenance.canonical_laya_runtime_provenance_summary_bytes(forged)
    with pytest.raises(FrozenInstanceError):
        evidence.origin_verified = True
    with pytest.raises((TypeError, ValueError)):
        replace(evidence, schema_version="private-schema-marker")
    for sealed in (
        evidence.plan.objects[0],
        evidence.plan,
        evidence.receipts[0].envelope,
        evidence.receipts[0],
        evidence,
    ):
        with pytest.raises((TypeError, ValueError)):
            replace(sealed)
    summary = provenance.canonical_laya_runtime_provenance_summary_bytes(evidence)
    assert EVIDENCE_SCHEMA.encode() in summary
    for item in plan.objects:
        assert item.sha1.encode() not in summary
        assert item.sha256.encode() not in summary
        assert item.repository.encode() not in summary
        assert item.sha1 not in repr(evidence)
        assert item.repository not in repr(evidence)


@pytest.mark.parametrize(
    "mutation",
    (
        "repository",
        "kind",
        "sha1",
        "size",
        "nonbytes",
        "container_type",
        "missing",
        "extra",
        "duplicate",
        "reordered",
    ),
)
def test_synthetic_aggregate_rejects_packet_authority_and_coverage_mutations(monkeypatch, mutation):
    provenance = _provenance()
    plan, packets, _ = _synthetic_profile(monkeypatch, provenance)
    first = packets[0]
    mutations = {
        "repository": ((CHECKPOINT_REPOSITORY, *first[1:]), *packets[1:]),
        "kind": ((first[0], "blob", *first[2:]), *packets[1:]),
        "sha1": ((first[0], first[1], "f" * 40, first[3]), *packets[1:]),
        "size": ((*first[:3], (first[3][0][:-1],)), *packets[1:]),
        "nonbytes": ((*first[:3], ("private-payload",)), *packets[1:]),
        "container_type": list(packets),
        "missing": packets[:-1],
        "extra": packets + (packets[-1],),
        "duplicate": (packets[0], packets[0], *packets[2:]),
        "reordered": (packets[1], packets[0], *packets[2:]),
    }
    with pytest.raises(ValueError) as caught:
        provenance.verify_laya_runtime_provenance_objects(plan, mutations[mutation])
    _private_error(caught.value, "private-payload")


def test_synthetic_aggregate_rejects_independent_sha256_authority(monkeypatch):
    provenance = _provenance()
    plan, packets, _ = _synthetic_profile(monkeypatch, provenance)
    wrong = _forge_exact(plan.objects[0], sha256="f" * 64)
    objects = (wrong, *plan.objects[1:])
    monkeypatch.setattr(provenance, "PROVENANCE_OBJECTS", objects)
    corrupt_plan = _forge_exact(plan, objects=objects)

    with pytest.raises(ValueError):
        provenance.verify_laya_runtime_provenance_objects(corrupt_plan, packets)


def test_synthetic_dag_rejects_cross_swapped_edges_modes_and_lfs_authorities(
    monkeypatch,
):
    provenance = _provenance()
    plan, packets, payloads = _synthetic_profile(monkeypatch, provenance)
    by_role = {item.role: item for item in plan.objects}
    for role in ("weights_lfs", "tokenizer_lfs"):
        parsed = provenance._parse_lfs_pointer_bytes(payloads[role])
        spec = by_role[role]
        assert spec.sha1 != spec.sha256[:40]
        assert parsed.sha256 != spec.sha256
        assert parsed.sha256 != spec.sha1
    role_positions = {item.role: index for index, item in enumerate(plan.objects)}
    for left, right in (
        ("source_tag", "source_commit"),
        ("source_commit", "checkpoint_commit"),
        ("source_tree", "checkpoint_tree"),
        ("encoder_tree", "tokenizer_tree"),
        ("weights_lfs", "tokenizer_lfs"),
    ):
        mutated = list(packets)
        a, b = role_positions[left], role_positions[right]
        mutated[a], mutated[b] = mutated[b], mutated[a]
        with pytest.raises(ValueError):
            provenance.verify_laya_runtime_provenance_objects(plan, tuple(mutated))

    identities = {item.role: item.sha1 for item in plan.objects}
    graph_mutations = []
    changed = dict(payloads)
    changed["source_tag"] = _tag(identities["checkpoint_commit"])
    graph_mutations.append((changed, None, None))
    changed = dict(payloads)
    changed["source_commit"] = _commit(identities["checkpoint_tree"])
    new_source_commit = _git_sha1("commit", changed["source_commit"])
    changed["source_tag"] = _tag(new_source_commit)
    graph_mutations.append((changed, new_source_commit, None))
    for license_mode, license_target in (
        ("100644", "source_pyproject"),
        ("040000", "source_license"),
    ):
        changed = dict(payloads)
        changed["source_tree"] = b"".join(
            (
                _tree_entry(
                    license_mode,
                    "LICENSE",
                    identities[license_target],
                ),
                _tree_entry("100644", "pyproject.toml", identities["source_pyproject"]),
            )
        )
        changed["source_commit"] = _commit(_git_sha1("tree", changed["source_tree"]))
        new_source_commit = _git_sha1("commit", changed["source_commit"])
        changed["source_tag"] = _tag(new_source_commit)
        graph_mutations.append((changed, new_source_commit, None))
    changed = dict(payloads)
    changed["checkpoint_tree"] = b"".join(
        (
            _tree_entry("100644", "README.md", identities["checkpoint_readme"]),
            _tree_entry("040000", "multilingual", identities["encoder_tree"]),
        )
    )
    changed["checkpoint_commit"] = _commit(_git_sha1("tree", changed["checkpoint_tree"]))
    graph_mutations.append((changed, None, _git_sha1("commit", changed["checkpoint_commit"])))
    for changed, source_commit, checkpoint_commit in graph_mutations:
        monkeypatch.setattr(
            provenance,
            "SOURCE_COMMIT",
            source_commit or _git_sha1("commit", changed["source_commit"]),
        )
        monkeypatch.setattr(
            provenance,
            "CHECKPOINT_COMMIT",
            checkpoint_commit or _git_sha1("commit", changed["checkpoint_commit"]),
        )
        corrupt_plan, corrupt_packets = _rebind_synthetic_profile(
            monkeypatch, provenance, plan, changed
        )
        with pytest.raises(ValueError):
            provenance.verify_laya_runtime_provenance_objects(corrupt_plan, corrupt_packets)
    weights_position = role_positions["weights_lfs"]
    pointer = packets[weights_position][3][0]
    for mutation in (
        pointer.replace(b"size 17", b"size 18"),
        pointer.replace(pointer.split(b"sha256:", 1)[1][:64], b"f" * 64),
    ):
        mutated = list(packets)
        mutated[weights_position] = (*packets[weights_position][:3], (mutation,))
        with pytest.raises(ValueError):
            provenance.verify_laya_runtime_provenance_objects(plan, tuple(mutated))


def test_invalid_exact_pr34_ancestry_fails_before_object_iterable_is_touched(
    monkeypatch,
):
    provenance = _provenance()
    checkpoint = _checkpoint_evidence(monkeypatch)

    class Untouched:
        def __iter__(self):
            raise AssertionError("private-stream-marker")

    bad_receipt = _forge_exact(checkpoint.receipts[0], checkpoint_file_bytes_verified=False)
    file_corruptions = []
    first_file = checkpoint.plan.files[0]
    for changes in (
        {"role": "private-role-marker"},
        {"path": "private/path-marker"},
        {"size_bytes": first_file.size_bytes + 1},
        {"sha256": "f" * 64},
    ):
        bad_file = _forge_exact(first_file, **changes)
        bad_plan = _forge_exact(checkpoint.plan, files=(bad_file, *checkpoint.plan.files[1:]))
        bad_receipts = (
            _forge_exact(checkpoint.receipts[0], plan=bad_plan, file=bad_file),
            *(_forge_exact(receipt, plan=bad_plan) for receipt in checkpoint.receipts[1:]),
        )
        file_corruptions.append(_forge_exact(checkpoint, plan=bad_plan, receipts=bad_receipts))
    corruptions = (
        _forge_exact(checkpoint, runtime_identity=SimpleNamespace(sha256="f" * 64)),
        _forge_exact(checkpoint, receipts=(bad_receipt, *checkpoint.receipts[1:])),
        _forge_exact(checkpoint, receipts=tuple(reversed(checkpoint.receipts))),
        _forge_exact(
            checkpoint, plan=_forge_exact(checkpoint.plan, files=checkpoint.plan.files[:-1])
        ),
        _forge_exact(
            checkpoint,
            deployment_evidence=_forge_exact(
                checkpoint.deployment_evidence,
                checkpoint_manifest=_forge_exact(
                    checkpoint.deployment_evidence.checkpoint_manifest,
                    revision="f" * 40,
                ),
            ),
        ),
        *file_corruptions,
        _forge_exact(
            checkpoint,
            deployment_evidence=_forge_exact(
                checkpoint.deployment_evidence,
                checkpoint_manifest=_forge_exact(
                    checkpoint.deployment_evidence.checkpoint_manifest,
                    subfolder="private-subfolder-marker",
                ),
            ),
        ),
        _forge_exact(
            checkpoint,
            deployment_evidence=_forge_exact(
                checkpoint.deployment_evidence,
                snapshot=_forge_exact(
                    checkpoint.deployment_evidence.snapshot,
                    artifacts=tuple(reversed(checkpoint.deployment_evidence.snapshot.artifacts)),
                ),
            ),
        ),
        _forge_exact(
            checkpoint,
            deployment_evidence=_forge_exact(
                checkpoint.deployment_evidence,
                snapshot=_forge_exact(
                    checkpoint.deployment_evidence.snapshot,
                    runtime_identity=SimpleNamespace(sha256="e" * 64),
                ),
            ),
        ),
        _forge_exact(
            checkpoint,
            deployment_evidence=_forge_exact(
                checkpoint.deployment_evidence,
                snapshot=_forge_exact(
                    checkpoint.deployment_evidence.snapshot,
                    artifacts=(
                        _forge_exact(
                            checkpoint.deployment_evidence.snapshot.artifacts[0],
                            content=b"private-artifact-marker",
                        ),
                        *checkpoint.deployment_evidence.snapshot.artifacts[1:],
                    ),
                ),
            ),
        ),
    )
    for invalid in corruptions:
        with pytest.raises(ValueError) as caught:
            provenance.prepare_laya_runtime_provenance_plan(invalid)
        _private_error(
            caught.value,
            "private-stream-marker",
            "private-subfolder-marker",
            "private-role-marker",
            "private/path-marker",
            "private-artifact-marker",
        )
    with pytest.raises((TypeError, ValueError)):
        provenance.verify_laya_runtime_provenance_objects(SimpleNamespace(), Untouched())


def test_prepare_rejects_fabricated_exact_checkpoint_evidence():
    provenance = _provenance()
    from tests.test_laya_runtime_checkpoint import _fabricated_checkpoint_evidence

    fabricated = _fabricated_checkpoint_evidence()
    with pytest.raises(ValueError):
        provenance.prepare_laya_runtime_provenance_plan(fabricated)


def test_fabricated_checkpoint_plan_is_rejected_before_object_stream_consumption(
    monkeypatch,
):
    provenance = _provenance()
    from tests.test_laya_runtime_checkpoint import _fabricated_checkpoint_evidence

    legitimate_plan, packets, _ = _synthetic_profile(monkeypatch, provenance)
    fabricated = _fabricated_checkpoint_evidence()
    forged_plan = _forge_exact(
        legitimate_plan,
        checkpoint_evidence=fabricated,
        runtime_identity=fabricated.runtime_identity,
    )

    class Untouched:
        requested = 0

        def __iter__(self):
            return self

        def __next__(self):
            self.requested += 1
            raise AssertionError("private-forged-checkpoint-stream")

    chunks = Untouched()
    with pytest.raises(ValueError) as caught:
        provenance._verify_laya_runtime_provenance_object_chunks(
            forged_plan, forged_plan.objects[0].sha1, chunks
        )
    assert chunks.requested == 0
    _private_error(caught.value, "private-forged-checkpoint-stream")
    assert packets


@pytest.mark.parametrize(
    ("cap", "value"),
    (
        ("MAX_PROVENANCE_TOTAL_BYTES", 1),
        ("MAX_PROVENANCE_TREE_ENTRIES", 3),
        ("MAX_PROVENANCE_PATH_COMPONENTS", 2),
        ("MAX_PROVENANCE_DAG_VISITS", 15),
    ),
)
def test_synthetic_profile_caps_fail_closed_before_evidence(monkeypatch, cap, value):
    provenance = _provenance()
    plan, packets, _ = _synthetic_profile(monkeypatch, provenance)
    monkeypatch.setattr(provenance, cap, value)
    with pytest.raises(ValueError):
        provenance.verify_laya_runtime_provenance_objects(plan, packets)


def _receipts_with_envelope_mutation(evidence, role, **changes):
    receipts = list(evidence.receipts)
    position = next(index for index, receipt in enumerate(receipts) if receipt.spec.role == role)
    envelope = _forge_exact(receipts[position].envelope, **changes)
    receipts[position] = _forge_exact(receipts[position], envelope=envelope)
    return tuple(receipts)


def test_exact_class_clones_cannot_self_assert_provenance_without_verified_bytes(
    monkeypatch,
):
    provenance = _provenance()
    plan, packets, _ = _synthetic_profile(monkeypatch, provenance)
    evidence = provenance.verify_laya_runtime_provenance_objects(plan, packets)
    cloned_receipts = tuple(
        _forge_exact(receipt, envelope=_forge_exact(receipt.envelope))
        for receipt in evidence.receipts
    )
    forged_evidence = _forge_exact(evidence, receipts=cloned_receipts)

    with pytest.raises(ValueError) as sealed:
        provenance._seal_laya_runtime_provenance_evidence(plan, cloned_receipts)
    _private_error(sealed.value)
    with pytest.raises(ValueError) as summarized:
        provenance.canonical_laya_runtime_provenance_summary_bytes(forged_evidence)
    _private_error(summarized.value)

    def clone_private_slots(instance, **changes):
        clone = _forge_exact(instance, **changes)
        for name in ("_factory_capability", "_semantic_capability"):
            if hasattr(instance, name):
                object.__setattr__(clone, name, getattr(instance, name))
        return clone

    replayed_receipts = tuple(
        clone_private_slots(
            receipt,
            envelope=clone_private_slots(receipt.envelope),
        )
        for receipt in evidence.receipts
    )
    replayed_evidence = clone_private_slots(evidence, receipts=replayed_receipts)
    with pytest.raises(ValueError):
        provenance._seal_laya_runtime_provenance_evidence(plan, replayed_receipts)
    with pytest.raises(ValueError):
        provenance.canonical_laya_runtime_provenance_summary_bytes(replayed_evidence)

    identity_cloned_receipts = tuple(clone_private_slots(receipt) for receipt in evidence.receipts)
    identity_cloned_evidence = clone_private_slots(evidence)
    with pytest.raises(ValueError):
        provenance._seal_laya_runtime_provenance_evidence(
            plan,
            identity_cloned_receipts,
        )
    with pytest.raises(ValueError):
        provenance.canonical_laya_runtime_provenance_summary_bytes(
            identity_cloned_evidence,
        )


@pytest.mark.parametrize(
    ("role", "changes"),
    (
        ("source_tag", {"target_kind": "tree"}),
        ("source_tag", {"tag_name": "private-tag-marker"}),
        ("source_tag", {"tree_sha1": "f" * 40}),
        ("source_commit", {"tree_sha1": None}),
        ("source_commit", {"parent_sha1s": ("f" * 40,)}),
        ("source_commit", {"target_kind": "commit"}),
        ("source_tree", {"tree_entries": ()}),
        ("source_tree", {"lfs_sha256": "f" * 64, "lfs_size_bytes": 1}),
        ("encoder_config", {"tree_sha1": "f" * 40}),
        ("weights_lfs", {"lfs_sha256": None}),
        ("weights_lfs", {"source_license_declared": True}),
        ("source_license", {"source_license_declared": False}),
        ("source_pyproject", {"source_license_declared": False}),
        ("checkpoint_readme", {"checkpoint_license_declared": False}),
        ("laya_config", {"checkpoint_license_declared": True}),
    ),
)
def test_envelope_derived_fields_are_closed_by_role(monkeypatch, role, changes):
    provenance = _provenance()
    plan, packets, _ = _synthetic_profile(monkeypatch, provenance)
    evidence = provenance.verify_laya_runtime_provenance_objects(plan, packets)
    receipts = _receipts_with_envelope_mutation(evidence, role, **changes)
    forged = _forge_exact(evidence, receipts=receipts)

    with pytest.raises(ValueError) as sealed:
        provenance._seal_laya_runtime_provenance_evidence(plan, receipts)
    _private_error(sealed.value, "private-tag-marker")
    with pytest.raises(ValueError) as summarized:
        provenance.canonical_laya_runtime_provenance_summary_bytes(forged)
    _private_error(summarized.value, "private-tag-marker")


def test_unit_verifier_revalidates_exact_pr34_ancestry_before_issuing_receipt(
    monkeypatch,
):
    provenance = _provenance()
    plan, packets, _ = _synthetic_profile(monkeypatch, provenance)
    original_checkpoint = plan.checkpoint_evidence
    hostile_identity = SimpleNamespace(
        schema_version=plan.runtime_identity.schema_version,
        sha256="f" * 64,
    )
    adulterated_checkpoint = object.__new__(type(original_checkpoint))
    object.__setattr__(adulterated_checkpoint, "plan", original_checkpoint.plan)
    object.__setattr__(adulterated_checkpoint, "runtime_identity", hostile_identity)
    adulterated_plan = _forge_exact(
        plan,
        checkpoint_evidence=adulterated_checkpoint,
        runtime_identity=hostile_identity,
    )

    def validate(value):
        if value is not original_checkpoint:
            raise ValueError("private-ancestor-marker")
        return value

    monkeypatch.setattr(provenance, "_deep_validate_checkpoint_evidence", validate)
    with pytest.raises(ValueError) as caught:
        provenance._verify_laya_runtime_provenance_object_chunks(
            adulterated_plan, adulterated_plan.objects[0].sha1, packets[0][3]
        )
    _private_error(caught.value, "private-ancestor-marker")


def test_aggregate_preflights_all_closed_chunk_containers_before_consuming_any(
    monkeypatch,
):
    provenance = _provenance()
    plan, packets, _ = _synthetic_profile(monkeypatch, provenance)
    requests = 0

    def counted(chunks):
        nonlocal requests
        for chunk in chunks:
            requests += 1
            yield chunk

    hostile = tuple(
        (*packet[:3], counted(packet[3])) if index < 15 else (*packet[:3], None)
        for index, packet in enumerate(packets)
    )
    with pytest.raises(ValueError):
        provenance.verify_laya_runtime_provenance_objects(plan, hostile)
    assert requests == 0

    for invalid in (
        [*packets],
        (*packets[:1], (*packets[1][:3], [*packets[1][3]]), *packets[2:]),
        (
            *packets[:1],
            (*packets[1][:3], (b"x",) * (provenance.MAX_PROVENANCE_CHUNKS + 1)),
            *packets[2:],
        ),
        (*packets[:1], (*packets[1][:3], (b"",)), *packets[2:]),
    ):
        with pytest.raises(ValueError):
            provenance.verify_laya_runtime_provenance_objects(plan, invalid)


def test_public_surface_is_closed():
    provenance = _provenance()
    expected = {
        "PROVENANCE_PLAN_SCHEMA",
        "PROVENANCE_EVIDENCE_SCHEMA",
        "SOURCE_REPOSITORY",
        "CHECKPOINT_REPOSITORY",
        "SOURCE_COMMIT",
        "CHECKPOINT_COMMIT",
        "MAX_PROVENANCE_OBJECTS",
        "MAX_PROVENANCE_OBJECT_BYTES",
        "MAX_PROVENANCE_TOTAL_BYTES",
        "MAX_PROVENANCE_CHUNK_BYTES",
        "MAX_PROVENANCE_CHUNKS",
        "MAX_PROVENANCE_TREE_ENTRIES",
        "MAX_PROVENANCE_PATH_COMPONENTS",
        "MAX_PROVENANCE_DAG_VISITS",
        "PROVENANCE_OBJECTS",
        "LayaGitObjectSpec",
        "LayaRuntimeProvenancePlan",
        "LayaGitObjectEnvelope",
        "VerifiedLayaProvenanceObject",
        "LayaRuntimeProvenanceEvidence",
        "prepare_laya_runtime_provenance_plan",
        "verify_laya_runtime_provenance_objects",
        "canonical_laya_runtime_provenance_summary_bytes",
    }
    assert type(provenance.__all__) is tuple
    assert set(provenance.__all__) == expected
    assert len(provenance.__all__) == len(expected)
    assert not hasattr(provenance, "verify_laya_runtime_provenance_object_chunks")


def test_live_chunk_cap_never_exceeds_object_cap(monkeypatch):
    provenance = _provenance()
    assert 0 < provenance.MAX_PROVENANCE_CHUNK_BYTES <= provenance.MAX_PROVENANCE_OBJECT_BYTES

    plan, packets, _ = _synthetic_profile(monkeypatch, provenance)
    monkeypatch.setattr(provenance, "MAX_PROVENANCE_CHUNK_BYTES", 1)
    with pytest.raises(ValueError):
        provenance._verify_laya_runtime_provenance_object_chunks(
            plan, plan.objects[0].sha1, packets[0][3]
        )


def test_factory_sealed_types_are_frozen_slotted_private_and_retain_no_payload():
    provenance = _provenance()
    classes = (
        provenance.LayaGitObjectSpec,
        provenance.LayaRuntimeProvenancePlan,
        provenance.LayaGitObjectEnvelope,
        provenance.VerifiedLayaProvenanceObject,
        provenance.LayaRuntimeProvenanceEvidence,
    )
    for cls in classes:
        assert is_dataclass(cls) and cls.__dataclass_params__.frozen
        assert "__dict__" not in vars(cls)
        assert not {"payload", "content", "chunks", "raw_bytes"} & {
            field.name for field in fields(cls)
        }
        with pytest.raises((TypeError, ValueError)):
            cls()
    for cls in classes:
        token = inspect.signature(cls).parameters.get("_factory_token")
        assert token is not None and token.default is inspect.Parameter.empty


def test_caller_visible_provenance_capabilities_cannot_retarget_object_authority(
    monkeypatch,
):
    provenance = _provenance()
    plan, packets, _ = _synthetic_profile(monkeypatch, provenance)
    evidence = provenance.verify_laya_runtime_provenance_objects(plan, packets)
    receipt = evidence.receipts[0]
    envelope = receipt.envelope
    cloned_spec = _forge_exact(receipt.spec)
    object.__setattr__(plan, "objects", (cloned_spec, *plan.objects[1:]))
    object.__setattr__(envelope, "spec", cloned_spec)
    object.__setattr__(receipt, "spec", cloned_spec)
    object.__setattr__(plan, "_semantic_capability", provenance._plan_semantics(plan))
    object.__setattr__(
        envelope,
        "_semantic_capability",
        provenance._envelope_semantics(envelope),
    )
    object.__setattr__(
        receipt,
        "_semantic_capability",
        (id(plan), id(cloned_spec), id(envelope), True),
    )

    with pytest.raises(ValueError):
        provenance.canonical_laya_runtime_provenance_summary_bytes(evidence)


def test_evidence_claims_and_summary_remain_conservative_private_and_deep():
    provenance = _provenance()
    evidence_fields = {
        field.name: field for field in fields(provenance.LayaRuntimeProvenanceEvidence)
    }
    true_flags = {
        "artifact_integrity_verified",
        "runtime_config_semantics_verified",
        "checkpoint_manifest_semantics_verified",
        "checkpoint_bytes_verified",
        "provenance_objects_verified",
        "source_git_content_verified",
        "checkpoint_git_content_verified",
        "source_license_declaration_observed",
        "checkpoint_license_declaration_observed",
    }
    false_flags = {
        "lock_verified",
        "sbom_verified",
        "lock_sbom_consistent",
        "oci_bytes_verified",
        "oci_manifest_semantics_verified",
        "origin_verified",
        "license_verified",
        "base_ancestry_verified",
        "runtime_materialized",
        "executor_available",
        "inference_executed",
    }
    assert all(not evidence_fields[name].init for name in true_flags | false_flags)
    for value in (None, SimpleNamespace(), object()):
        with pytest.raises((TypeError, ValueError)):
            provenance.canonical_laya_runtime_provenance_summary_bytes(value)
    source = Path(provenance.__file__).read_text(encoding="utf-8")
    summary_source = source[source.index("def canonical_laya_runtime_provenance_summary_bytes") :]
    assert all(term not in summary_source for term in ('"path"', '"sha1"', '"sha256"', '"payload"'))


def test_module_is_pure_and_has_only_the_pr37_convergence_caller():
    provenance = _provenance()
    source = Path(provenance.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert not imports & {
        "os",
        "pathlib",
        "subprocess",
        "socket",
        "requests",
        "urllib",
        "shutil",
    }
    forbidden_builtin_calls = {"__import__", "compile", "eval", "exec", "open"}
    name_calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not name_calls & forbidden_builtin_calls
    forbidden_owners = {
        "os",
        "pathlib",
        "subprocess",
        "socket",
        "requests",
        "urllib",
        "shutil",
    }

    def owner_name(node):
        while isinstance(node, ast.Attribute):
            node = node.value
        return node.id if isinstance(node, ast.Name) else None

    assert (
        not {
            owner_name(node.func)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        & forbidden_owners
    )
    offenders = []
    for root in (Path("src"), Path("backend"), Path("scripts")):
        for path in root.rglob("*.py"):
            if path.as_posix() == "src/human_feedback/runtime_provenance.py":
                continue
            candidate = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(candidate):
                if isinstance(node, ast.Import) and any(
                    alias.name == "human_feedback.runtime_provenance" for alias in node.names
                ):
                    offenders.append(path.as_posix())
                    break
                if isinstance(node, ast.ImportFrom) and (
                    node.module == "human_feedback.runtime_provenance"
                    or (
                        node.module == "human_feedback"
                        and any(alias.name == "runtime_provenance" for alias in node.names)
                    )
                    or (
                        node.level > 0
                        and (
                            node.module == "runtime_provenance"
                            or (
                                node.module is None
                                and any(alias.name == "runtime_provenance" for alias in node.names)
                            )
                        )
                    )
                ):
                    offenders.append(path.as_posix())
                    break
                if (
                    isinstance(node, ast.Constant)
                    and node.value == "human_feedback.runtime_provenance"
                ):
                    offenders.append(path.as_posix())
                    break
    assert offenders == ["src/human_feedback/runtime_supply_convergence.py"]
